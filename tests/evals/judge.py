"""DeepEval model adapters.

- NoLLM: for deterministic metrics (ToolCorrectness) whose constructor wants a
  model but whose scoring never calls one. Raises if it ever is called, so a
  "deterministic" CI check can't silently become an LLM call.
- GroqJudge: OpenAI-compatible Groq endpoint as the LLM judge for
  PlanQuality / PlanAdherence / Faithfulness / GEval.
"""
import json
import os

import httpx
from deepeval.models import DeepEvalBaseLLM
from pydantic import BaseModel


class NoLLM(DeepEvalBaseLLM):
    def __init__(self):
        super().__init__(model="none")

    def load_model(self):
        return None

    def generate(self, *args, **kwargs):
        raise RuntimeError("deterministic metric attempted an LLM call")

    async def a_generate(self, *args, **kwargs):
        raise RuntimeError("deterministic metric attempted an LLM call")

    def get_model_name(self) -> str:
        return "none (deterministic)"


class GroqJudge(DeepEvalBaseLLM):
    def __init__(self, model: str | None = None):
        self.api_key = os.environ["GROQ_API_KEY"]
        super().__init__(model=model or os.getenv("JUDGE_MODEL", "openai/gpt-oss-120b"))

    def load_model(self):
        return None

    def _body(self, prompt: str, schema: type[BaseModel] | None) -> dict:
        body = {"model": self.name, "temperature": 0, "messages": [{"role": "user", "content": prompt}]}
        if schema is not None:
            body["response_format"] = {"type": "json_object"}
            body["messages"][0]["content"] += (
                "\n\nRespond with a single JSON object matching this JSON schema:\n"
                + json.dumps(schema.model_json_schema())
            )
        return body

    @staticmethod
    def _parse(resp: httpx.Response, schema):
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        return schema.model_validate_json(content) if schema is not None else content

    def generate(self, prompt: str, schema: type[BaseModel] | None = None):
        r = httpx.post("https://api.groq.com/openai/v1/chat/completions", json=self._body(prompt, schema),
                       headers={"Authorization": f"Bearer {self.api_key}"}, timeout=60)
        return self._parse(r, schema)

    async def a_generate(self, prompt: str, schema: type[BaseModel] | None = None):
        async with httpx.AsyncClient(timeout=60) as c:
            r = await c.post("https://api.groq.com/openai/v1/chat/completions", json=self._body(prompt, schema),
                             headers={"Authorization": f"Bearer {self.api_key}"})
        return self._parse(r, schema)

    def get_model_name(self) -> str:
        return f"groq/{self.name}"
