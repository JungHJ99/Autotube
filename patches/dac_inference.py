from pathlib import Path

import click
import hydra
import numpy as np
import pyrootutils
import soundfile as sf
import torch
import torchaudio
from hydra import compose, initialize
from hydra.utils import instantiate
from loguru import logger
from omegaconf import OmegaConf

pyrootutils.setup_root(__file__, indicator=".project-root", pythonpath=True)

from fish_speech.utils.file import AUDIO_EXTENSIONS

# register eval resolver
OmegaConf.register_new_resolver("eval", eval)


def load_model(config_name, checkpoint_path, device="cuda"):
    hydra.core.global_hydra.GlobalHydra.instance().clear()
    with initialize(version_base="1.3", config_path="../../configs"):
        cfg = compose(config_name=config_name)

    # autotube patch (2026-05-18): assemble everything on CPU in fp16 first, then
    # move to device. Upstream does `state_dict = torch.load(map_location=device)`
    # + `model.to(device)` while the model is still fp32, peaking at ~6.6 GiB
    # GPU and OOMing 8 GB cards. We instead:
    #   1. instantiate the model on CPU and immediately .half()
    #   2. torch.load state_dict to CPU (also weights_only=True so it's untrusted-safe)
    #   3. load_state_dict with assign=True so the fp16 weights take over directly
    #   4. del + gc + empty_cache to make sure nothing fp32 lingers
    #   5. .to(device) once, in fp16 — single ~1.9 GiB transfer instead of fp32 spike
    import gc
    def _mem(tag):
        if torch.cuda.is_available():
            logger.info(f"[autotube-mem] {tag}: alloc={torch.cuda.memory_allocated()/1e9:.2f}GB reserved={torch.cuda.memory_reserved()/1e9:.2f}GB")
    _mem("decoder load start")
    model = instantiate(cfg)
    _mem("after instantiate(cfg)")
    model.eval()
    model.half()
    _mem("after model.half() (on CPU)")

    # mmap=False ensures tensors are materialized fully in CPU RAM as fp16, so
    # subsequent .to(device, dtype=torch.float16) doesn't accidentally promote
    # back to fp32 mid-transfer (which was peaking GPU at 4.1 GiB for what
    # should be a 1.87 GiB fp16 model).
    state_dict = torch.load(
        checkpoint_path, map_location="cpu", mmap=False, weights_only=True
    )
    _mem("after torch.load(cpu)")
    if "state_dict" in state_dict:
        state_dict = state_dict["state_dict"]

    if any("generator" in k for k in state_dict):
        state_dict = {
            k.replace("generator.", ""): v
            for k, v in state_dict.items()
            if "generator." in k
        }

    # Cast checkpoint tensors to fp16 too (if not already), so assign=True keeps
    # the model in fp16.
    state_dict = {k: v.half() if v.is_floating_point() else v for k, v in state_dict.items()}

    result = model.load_state_dict(state_dict, strict=False, assign=True)
    _mem("after load_state_dict")
    del state_dict
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    _mem("after gc + empty_cache")
    # Explicit dtype on .to() — without this, mmap'd / assigned tensors can be
    # promoted back to fp32 during the host→device transfer, doubling VRAM.
    model.to(device=device, dtype=torch.float16)
    _mem("after model.to(device, fp16)")

    logger.info(f"Loaded model: {result}")
    return model


@torch.no_grad()
@click.command()
@click.option(
    "--input-path",
    "-i",
    default="test.wav",
    type=click.Path(exists=True, path_type=Path),
)
@click.option(
    "--output-path", "-o", default="fake.wav", type=click.Path(path_type=Path)
)
@click.option("--config-name", default="modded_dac_vq")
@click.option(
    "--checkpoint-path",
    default="checkpoints/openaudio-s1-mini/codec.pth",
)
@click.option(
    "--device",
    "-d",
    default="cuda",
)
def main(input_path, output_path, config_name, checkpoint_path, device):
    model = load_model(config_name, checkpoint_path, device=device)

    if input_path.suffix in AUDIO_EXTENSIONS:
        logger.info(f"Processing in-place reconstruction of {input_path}")

        # Load audio
        audio, sr = torchaudio.load(str(input_path))
        if audio.shape[0] > 1:
            audio = audio.mean(0, keepdim=True)
        audio = torchaudio.functional.resample(audio, sr, model.sample_rate)

        audios = audio[None].to(device)
        logger.info(
            f"Loaded audio with {audios.shape[2] / model.sample_rate:.2f} seconds"
        )

        # VQ Encoder
        audio_lengths = torch.tensor([audios.shape[2]], device=device, dtype=torch.long)
        indices, _ = model.encode(audios, audio_lengths)

        if indices.ndim == 3:
            indices = indices[0]

        logger.info(f"Generated indices of shape {indices.shape}")

        # Save indices
        np.save(output_path.with_suffix(".npy"), indices.cpu().numpy())
    elif input_path.suffix == ".npy":
        logger.info(f"Processing precomputed indices from {input_path}")
        indices = np.load(input_path)
        indices = torch.from_numpy(indices).to(device).long()
        assert indices.ndim == 2, f"Expected 2D indices, got {indices.ndim}"
        # indices_lens = torch.tensor([indices.shape[1]], device=device, dtype=torch.long)
    else:
        raise ValueError(f"Unknown input type: {input_path}")

    # Restore
    if indices.ndim == 2:
        indices = indices.unsqueeze(0)

    fake_audios = model.from_indices(indices)
    audio_time = fake_audios.shape[-1] / model.sample_rate

    logger.info(
        f"Generated audio of shape {fake_audios.shape}, equivalent to {audio_time:.2f} seconds from {indices.shape[1]} features, features/second: {indices.shape[1] / audio_time:.2f}"
    )

    # Save audio
    fake_audio = fake_audios[0, 0].float().cpu().numpy()
    sf.write(output_path, fake_audio, model.sample_rate)
    logger.info(f"Saved audio to {output_path}")


if __name__ == "__main__":
    main()
