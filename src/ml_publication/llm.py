"""Bedrock LLM helpers for multiple model families."""
from __future__ import annotations

import json

import boto3


class LLMError(RuntimeError):
    pass


def build_podcast_prompt(article_text: str, title: str | None = None, style: str = "podcast") -> str:
    title_line = f"Title: {title}\n" if title else ""
    return (
        "You are a podcast writer. Rewrite the following article into a natural, "
        "single-host podcast script. Keep it engaging, clear, and structured with an intro, "
        "3-5 short segments with signposts, and a concise outro. Aim for 6-10 minutes of speech. "
        "Use plain text only; do not include JSON, markdown, or stage directions.\n\n"
        f"Style: {style}\n"
        f"{title_line}"
        "Article:\n"
        f"{article_text}"
    )


def _is_nova_model(model_id: str) -> bool:
    return model_id.startswith("amazon.nova") or model_id.startswith("us.amazon.nova")


def _is_anthropic_model(model_id: str) -> bool:
    return model_id.startswith("anthropic.") or model_id.startswith("us.anthropic.")


def call_bedrock(model_id: str, prompt: str, max_tokens: int = 1400, temperature: float = 0.5) -> str:
    if _is_anthropic_model(model_id):
        return call_bedrock_anthropic(model_id, prompt, max_tokens=max_tokens, temperature=temperature)
    if _is_nova_model(model_id):
        return call_bedrock_nova(model_id, prompt, max_tokens=max_tokens, temperature=temperature)
    raise LLMError(f"Unsupported Bedrock model_id: {model_id}")


def call_bedrock_anthropic(
    model_id: str,
    prompt: str,
    max_tokens: int = 1400,
    temperature: float = 0.5,
) -> str:
    client = boto3.client("bedrock-runtime")

    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": [
            {"role": "user", "content": [{"type": "text", "text": prompt}]}
        ],
    }

    response = client.invoke_model(
        modelId=model_id,
        body=json.dumps(body),
        accept="application/json",
        contentType="application/json",
    )

    payload = json.loads(response["body"].read())
    content = payload.get("content")
    if not content:
        raise LLMError("Bedrock response missing content.")

    text = content[0].get("text") if isinstance(content, list) else None
    if not text:
        raise LLMError("Bedrock response missing text.")
    return text.strip()


def call_bedrock_nova(
    model_id: str,
    prompt: str,
    max_tokens: int = 1400,
    temperature: float = 0.5,
) -> str:
    client = boto3.client("bedrock-runtime")

    body = {
        "messages": [
            {"role": "user", "content": [{"text": prompt}]}
        ],
        "inferenceConfig": {
            "maxTokens": max_tokens,
            "temperature": temperature,
        },
    }

    response = client.invoke_model(
        modelId=model_id,
        body=json.dumps(body),
        accept="application/json",
        contentType="application/json",
    )

    payload = json.loads(response["body"].read())
    content_list = (
        payload.get("output", {})
        .get("message", {})
        .get("content", [])
    )
    text_block = next((item for item in content_list if "text" in item), None)
    if not text_block:
        raise LLMError("Nova response missing text.")
    return text_block["text"].strip()
