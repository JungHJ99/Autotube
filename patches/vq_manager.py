from typing import Callable

import torch
from loguru import logger

from fish_speech.models.dac.modded_dac import DAC


class VQManager:

    def __init__(self):
        # Make Pylance happy (attribut/method not defined...)
        self.decoder_model: DAC
        self.load_audio: Callable

    def decode_vq_tokens(self, codes):
        logger.info(f"VQ features: {codes.shape}")

        # autotube patch (2026-05-18): on an 8 GB GPU the LLAMA generation
        # leaves ~150 MB of intermediate caches around that PyTorch hasn't
        # released. Without flushing them, the decoder's first conv layer
        # OOMs by ~200 MB. Force the allocator to release cached blocks
        # before allocating decode activations.
        import gc
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        if isinstance(self.decoder_model, DAC):
            with torch.cuda.amp.autocast(enabled=False):
                # Decode in inference_mode to disable autograd bookkeeping.
                with torch.inference_mode():
                    out = self.decoder_model.from_indices(codes[None])[0].squeeze()
            # Free decoder scratch memory before the next chunk's gen step.
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            return out

        raise ValueError(f"Unknown model type: {type(self.decoder_model)}")

    def encode_reference(self, reference_audio, enable_reference_audio):
        if enable_reference_audio and reference_audio is not None:
            # Load audios, and prepare basic info here
            if hasattr(self.decoder_model, "spec_transform"):
                sample_rate = self.decoder_model.spec_transform.sample_rate
            else:
                sample_rate = self.decoder_model.sample_rate
            reference_audio_content = self.load_audio(reference_audio, sample_rate)

            # autotube patch (2026-05-18): cast input audio to the decoder's
            # dtype. We force-fp16'd the decoder in patches/dac_inference.py to
            # fit an 8 GB GPU, but reference audio is still loaded as fp32 by
            # default. Without this cast, the fp16 decoder's biases mismatch
            # the fp32 input and convolutions raise:
            #   "Input type (float) and bias type (c10::Half) should be the same"
            _decoder_dtype = next(self.decoder_model.parameters()).dtype
            audios = torch.from_numpy(reference_audio_content).to(
                device=self.decoder_model.device,
                dtype=_decoder_dtype,
            )[None, None, :]
            audio_lengths = torch.tensor(
                [audios.shape[2]], device=self.decoder_model.device, dtype=torch.long
            )
            logger.info(
                f"Loaded audio with {audios.shape[2] / sample_rate:.2f} seconds"
            )

            # VQ Encoder
            if isinstance(self.decoder_model, DAC):
                prompt_tokens = self.decoder_model.encode(audios, audio_lengths)[0][0]
                logger.info(f"Encoded prompt: {prompt_tokens.shape}")
            else:
                raise ValueError(f"Unknown model type: {type(self.decoder_model)}")
        else:
            prompt_tokens = None
            logger.info("No reference audio provided")

        return prompt_tokens
