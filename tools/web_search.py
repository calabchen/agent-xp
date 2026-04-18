import os
from dotenv import load_dotenv
import json
import requests
from .base_tool import BaseTool


class WebSearchTool(BaseTool):
    def __init__(self):
        load_dotenv()
        super().__init__(
            name="web_search",
            description="Search the web for information. Input is a query. e.g. 'Champion of the 2024 Champions League'.",
        )

        self.api_key = os.getenv("BOCHA_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Missing API KEY: Please set 'BOCHA_API_KEY' in the .env file."
            )

        self.url = "https://api.bocha.cn/v1/web-search"

    def run(self, query: str) -> list:
        if not query or not query.strip():
            return [{"error": "Query cannot be empty."}]

        payload = json.dumps({"query": query, "summary": True, "count": 10})

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.request("POST", self.url, headers=headers, data=payload)
            response.raise_for_status()

            search_data = response.json()

            if not search_data or "data" not in search_data:
                return [{"error": "No search results available."}]

            formatted_results = []

            items = search_data.get("data", {}).get("webPages", {}).get("value", [])

            for item in items:
                formatted_result = {
                    "name": item.get("name", "No title available"),
                    "snippet": item.get("snippet", "No content available"),
                    "url": item.get("url", "No url available"),
                    "datepublished": item.get(
                        "datePublished", "No date published available"
                    ),
                }
                formatted_results.append(formatted_result)

            return (
                formatted_results
                if formatted_results
                else [{"error": "No results found."}]
            )

        except Exception as e:
            return [{"error": f"Search request failed: {str(e)}"}]


# === For standalone testing ===
if __name__ == "__main__":
    queries = ["F1 winner 2024"]
    web_search_tool = WebSearchTool()

    for query in queries:
        results = web_search_tool.run(query)
        if results:
            print(f"Context for '{query}':")
            for res in results:
                print(res)
            print("\n")
        else:
            print(f"No context found for '{query}'\n")
