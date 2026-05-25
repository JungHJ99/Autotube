import base64
import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional, Union

import torch

if TYPE_CHECKING:
    from transformers import PreTrainedTokenizerFast

logger = logging.getLogger(__name__)

# Constants definitions
# autotube patch (2026-05-18): aligned to OpenAudio S1-mini's special_tokens.json.
# Upstream constants said "<|endoftext|>" and "<|audio_pad|>" but the actual
# S1-mini checkpoint ships "<|end_of_text|>" and "<|audio|>" instead. These
# constants are only used to populate ALL_SPECIAL_TOKENS below; updating them
# keeps the helper list accurate (no external consumer references the legacy
# names — verified by grepping /app/fish_speech and /app/tools).
EOS_TOKEN = "<|end_of_text|>"
PAD_TOKEN = "<|pad|>"
IM_START_TOKEN = "<|im_start|>"
IM_END_TOKEN = "<|im_end|>"
PHONEME_START_TOKEN = "<|phoneme_start|>"
PHONEME_END_TOKEN = "<|phoneme_end|>"

MODALITY_TEXT_TOKEN = "<|text|>"
MODALITY_VOICE_TOKEN = "<|voice|>"
MODALITY_INTERLEAVE_TOKEN = "<|interleave|>"
AUDIO_START_TOKEN = "<|audio_start|>"
AUDIO_END_TOKEN = "<|audio_end|>"
AUDIO_EMBED_TOKEN = "<|audio|>"

MODALITY_TOKENS = {
    "text": MODALITY_TEXT_TOKEN,
    "voice": MODALITY_VOICE_TOKEN,
    "interleave": MODALITY_INTERLEAVE_TOKEN,
}

SEMANTIC_TOKEN_TEMPLATE = "<|semantic:{i}|>"
SEMANTIC_TOKENS = [SEMANTIC_TOKEN_TEMPLATE.format(i=i) for i in range(4096)]

ALL_SPECIAL_TOKENS = [
    EOS_TOKEN,
    PAD_TOKEN,
    IM_START_TOKEN,
    IM_END_TOKEN,
    PHONEME_START_TOKEN,
    PHONEME_END_TOKEN,
    MODALITY_TEXT_TOKEN,
    MODALITY_VOICE_TOKEN,
    MODALITY_INTERLEAVE_TOKEN,
    AUDIO_START_TOKEN,
    AUDIO_END_TOKEN,
    AUDIO_EMBED_TOKEN,
    *SEMANTIC_TOKENS,
]


# autotube patch (2026-05-18): OpenAudio S1-mini ships tokenizer.tiktoken +
# special_tokens.json (raw tiktoken format), not a transformers-style directory
# with tokenizer.json / tokenizer_config.json. Upstream FishTokenizer calls
# AutoTokenizer.from_pretrained(...) which fails on this layout (the directory
# has no model_type that Transformers recognizes — config.json declares
# "model_type": "dual_ar"). We wrap a raw tiktoken.Encoding with the subset of
# the transformers tokenizer API that FishTokenizer / content_sequence.py
# actually use: encode(), decode(), get_vocab(), convert_tokens_to_ids(),
# vocab_size, pad_token_id, eos_token_id, save_pretrained().
#
# The pat_str regex is the cl100k_base / Qwen2 pattern. S1-mini's BPE vocab
# size is exactly 151,643 (matches Qwen2), and the special-token layout
# matches Qwen2's <|im_start|>/<|im_end|> conventions, so this is almost
# certainly the right pattern. If Korean tokenization comes out garbled, the
# regex is the first thing to swap.
class _TikTokenWrapper:
    """
    Minimal duck-type of transformers.PreTrainedTokenizerFast over a raw
    tiktoken.Encoding. Only methods/properties touched by FishTokenizer and
    content_sequence are implemented.
    """

    # cl100k_base / Qwen2 pat_str. tiktoken uses fancy_regex which supports
    # \p{L} / \p{N} unicode classes natively.
    _PAT_STR = (
        r"(?i:'s|'t|'re|'ve|'m|'ll|'d)"
        r"|[^\r\n\p{L}\p{N}]?\p{L}+"
        r"|\p{N}{1,3}"
        r"| ?[^\s\p{L}\p{N}]+[\r\n]*"
        r"|\s*[\r\n]+"
        r"|\s+(?!\S)"
        r"|\s+"
    )

    def __init__(self, model_path: str):
        import tiktoken

        model_dir = Path(model_path)
        tiktoken_path = model_dir / "tokenizer.tiktoken"
        special_tokens_path = model_dir / "special_tokens.json"

        # Parse the tiktoken file: each line is "<base64-token-bytes> <rank>"
        mergeable_ranks = {}
        with tiktoken_path.open("r", encoding="utf-8") as f:
            for line in f:
                parts = line.split()
                if len(parts) < 2:
                    continue
                try:
                    token_bytes = base64.b64decode(parts[0])
                    rank = int(parts[1])
                except (ValueError, Exception) as e:
                    logger.warning(f"Skipping malformed tiktoken line: {line!r} ({e})")
                    continue
                mergeable_ranks[token_bytes] = rank

        with special_tokens_path.open("r", encoding="utf-8") as f:
            special_tokens = json.load(f)

        logger.info(
            f"Loading tiktoken tokenizer: {len(mergeable_ranks)} BPE merges, "
            f"{len(special_tokens)} special tokens from {model_dir}"
        )

        self._enc = tiktoken.Encoding(
            name="fish-s1-mini",
            pat_str=self._PAT_STR,
            mergeable_ranks=mergeable_ranks,
            special_tokens=special_tokens,
        )
        self._special_tokens = dict(special_tokens)

        # Build a vocab dict for FishTokenizer.__init__'s SEMANTIC scan. Include:
        #   (a) all special tokens (string -> id) — required for semantic lookup
        #   (b) UTF-8-decodable BPE tokens — for completeness, optional
        vocab = dict(special_tokens)
        for token_bytes, idx in mergeable_ranks.items():
            try:
                key = token_bytes.decode("utf-8")
            except UnicodeDecodeError:
                continue
            # Don't shadow a special token if there's a UTF-8 collision
            if key not in vocab:
                vocab[key] = idx
        self._vocab = vocab

        # Total vocab size = max id + 1 (specials extend past the BPE range)
        max_id = max(
            max(mergeable_ranks.values()) if mergeable_ranks else -1,
            max(special_tokens.values()) if special_tokens else -1,
        )
        self._vocab_size = max_id + 1

        # EOS / PAD: resolve from the special-tokens dict. Upstream Qwen-style
        # checkpoints use <|end_of_text|> as EOS, <|pad|> as PAD.
        self._eos_token_id = special_tokens.get(EOS_TOKEN)
        self._pad_token_id = special_tokens.get(PAD_TOKEN)
        if self._eos_token_id is None:
            # Fall back to <|im_end|> if some checkpoint variant uses that
            self._eos_token_id = special_tokens.get(IM_END_TOKEN)

    # ---- transformers-like API ----

    @property
    def vocab_size(self) -> int:
        return self._vocab_size

    @property
    def pad_token_id(self) -> Optional[int]:
        return self._pad_token_id

    @property
    def eos_token_id(self) -> Optional[int]:
        return self._eos_token_id

    def get_vocab(self):
        return dict(self._vocab)

    def convert_tokens_to_ids(self, tokens):
        # FishTokenizer.get_token_id passes a single token string.
        if isinstance(tokens, str):
            return self._vocab.get(tokens)
        return [self._vocab.get(t) for t in tokens]

    def encode(
        self,
        text: str,
        add_special_tokens: bool = False,
        allowed_special="all",
        **kwargs,
    ) -> List[int]:
        # tiktoken.Encoding.encode signature does NOT accept add_special_tokens.
        # FishTokenizer.encode always passes it; swallow it here.
        # Note: the `allowed_special` keyword is intentionally present in this
        # signature so that FishTokenizer's inspect.signature() check detects
        # us as a tiktoken-style backend and routes specials correctly.
        if allowed_special is None:
            allowed_special = set()
        return self._enc.encode(text, allowed_special=allowed_special)

    def decode(self, tokens, **kwargs) -> str:
        if isinstance(tokens, int):
            tokens = [tokens]
        # tiktoken Encoding.decode wants list[int]; tolerate tensors too
        if hasattr(tokens, "tolist"):
            tokens = tokens.tolist()
        return self._enc.decode(list(tokens))

    def save_pretrained(self, path: str):
        # No-op: the S1-mini checkpoint dir is already canonical. Re-saving
        # would require regenerating tokenizer.tiktoken which we don't have
        # a reason to do.
        logger.info(f"_TikTokenWrapper.save_pretrained({path}) — no-op")


def _is_tiktoken_dir(model_path: str) -> bool:
    p = Path(model_path)
    return (
        p.is_dir()
        and (p / "tokenizer.tiktoken").is_file()
        and (p / "special_tokens.json").is_file()
    )


class FishTokenizer:
    def __init__(self, model_path: str):
        # autotube patch (2026-05-18): if the checkpoint dir contains tiktoken
        # files, use the raw tiktoken wrapper instead of AutoTokenizer, which
        # would fail on the dual_ar model_type. Otherwise fall back to upstream
        # behavior (transformers AutoTokenizer for HF-format checkpoints).
        if _is_tiktoken_dir(model_path):
            logger.info(f"FishTokenizer: using tiktoken backend for {model_path}")
            self._tokenizer = _TikTokenWrapper(model_path)
        else:
            from transformers import AutoTokenizer
            self._tokenizer = AutoTokenizer.from_pretrained(model_path)
        self.semantic_id_to_token_id = {}

        vocab = self._tokenizer.get_vocab()
        valid_ids = []

        for code_idx in range(4096):
            token = SEMANTIC_TOKEN_TEMPLATE.format(i=code_idx)
            if token in vocab:
                token_id = vocab[token]
                self.semantic_id_to_token_id[code_idx] = token_id
                valid_ids.append(token_id)

        if not valid_ids:
            logger.error(
                "CRITICAL ERROR: No semantic tokens found in vocab! Audio cannot be synthesized."
            )
            self.semantic_begin_id = 0
            self.semantic_end_id = 0
            # Dummy tensor to prevent crash, though generation will fail
            self.semantic_map_tensor = torch.zeros(4096, dtype=torch.long)
        else:
            self.semantic_begin_id = min(valid_ids)
            self.semantic_end_id = max(valid_ids)
            # Create a lookup tensor to handle potential gaps in token IDs safely
            self.semantic_map_tensor = torch.zeros(4096, dtype=torch.long)
            for k, v in self.semantic_id_to_token_id.items():
                self.semantic_map_tensor[k] = v

        logger.info(
            f"Loaded Tokenizer. Semantic Range: {self.semantic_begin_id} -> {self.semantic_end_id}"
        )

    @property
    def vocab_size(self):
        return self._tokenizer.vocab_size

    @property
    def pad_token_id(self):
        return self._tokenizer.pad_token_id

    @property
    def eos_token_id(self):
        return self._tokenizer.eos_token_id

    def get_token_id(self, token: str) -> int:
        return self._tokenizer.convert_tokens_to_ids(token)

    def encode(
        self, text: str, add_special_tokens: bool = False, **kwargs
    ) -> List[int]:
        # [FIX] Force Qwen/Tiktoken backends to parse special tokens inline
        import inspect

        sig = inspect.signature(self._tokenizer.encode)
        if "allowed_special" in sig.parameters and "allowed_special" not in kwargs:
            kwargs["allowed_special"] = "all"
        return self._tokenizer.encode(
            text, add_special_tokens=add_special_tokens, **kwargs
        )

    def decode(self, tokens: Union[List[int], int], **kwargs) -> str:
        return self._tokenizer.decode(tokens, **kwargs)

    def save_pretrained(self, path: str):
        self._tokenizer.save_pretrained(path)

    @classmethod
    def from_pretrained(cls, path: str):
        return cls(path)

    def __getattr__(self, name):
        return getattr(self._tokenizer, name)
