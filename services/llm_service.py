from langchain_ollama import ChatOllama


class LLMService:
    """Generate text using the local conversational model through LangChain."""

    def __init__(self) -> None:
        self.model = ChatOllama(
            model="qwen3:1.7b",
            temperature=0,
            reasoning=False,
        )

    def invoke(self, prompt: str) -> str:
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("The prompt must not be empty.")
        response = self.model.invoke(prompt)
        return response.text


if __name__ == "__main__":
    service = LLMService()
    prompts = [
        "You are a customer support assistant. In one sentence, explain "
        "what a support ticket is.",
        "Classify the following customer support question into exactly one "
        "category:\n\nCUSTOMER: customer profiles or support ticket history.\n"
        "POLICY: company policies, including returns and refunds.\n\nQuestion:\n"
        '"What is Apple\'s return policy?"\n\nReturn only the category name.',
    ]
    print(f"{'=' * 50}\nLOCAL LLM TEST\n{'=' * 50}", flush=True)
    print(f"\nModel: {service.model.model}", flush=True)
    for index, prompt in enumerate(prompts, start=1):
        print(f"\nTest {index}\nPrompt:\n{prompt}", flush=True)
        response = service.invoke(prompt)
        if not response.strip():
            raise RuntimeError("The local model returned an empty response.")
        print(f"\nResponse:\n{response}", flush=True)
        if index == 2:
            print(f"\nClassification matches POLICY: {response.strip() == 'POLICY'}")
