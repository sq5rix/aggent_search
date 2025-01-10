from typing import Dict, List, Optional

import ollama
import requests
import trafilatura
from bs4 import BeautifulSoup

from .search_messages import CONTAINS_DATA_MSG, QUERY_GENERATOR_MSG

MODEL = "llama3.1:8b-instruct-q4_K_M"


class AISearchTool:
    def __init__(self, model_name: str = MODEL):
        self.model = model_name
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari"
        }

    def generate_search_query(self, prompt: str) -> str:
        """Generate a search query based on the prompt."""
        response = ollama.chat(
            model=self.model,
            messages=[
                {"role": "system", "content": QUERY_GENERATOR_MSG},
                {
                    "role": "user",
                    "content": f"CREATE A SEARCH QUERY FOR THIS PROMPT: \n{prompt}",
                },
            ],
        )
        query = response["message"]["content"]
        return query.strip('"')

    def search_duckduckgo(self, query: str) -> List[Dict]:
        """Perform DuckDuckGo search and return results."""
        url = f"https://html.duckduckgo.com/html?q={query}"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        results = []

        for i, result in enumerate(soup.find_all("div", class_="result"), start=1):
            if i > 10:
                break

            title_tag = result.find("a", class_="result__a")
            if not title_tag:
                continue

            link = title_tag["href"]
            snippet_tag = result.find("a", class_="result__snippet")
            snippet = (
                snippet_tag.text.strip() if snippet_tag else "No description available"
            )

            results.append({"id": i, "link": link, "search_description": snippet})

        return results

    def extract_content(self, url: str) -> Optional[str]:
        """Extract main content from webpage using trafilatura."""
        try:
            downloaded = trafilatura.fetch_url(url)
            text = trafilatura.extract(
                downloaded, include_links=False, include_images=False
            )
            return text
        except Exception:
            return None

    def verify_content_relevance(self, content: str, query: str, prompt: str) -> bool:
        """Verify if the content contains needed information."""
        needed_prompt = (
            f"PAGE_TEXT: {content} \nUSER_PROMPT: {prompt} \nSEARCH_QUERY: {query}"
        )

        response = ollama.chat(
            model=self.model,
            messages=[
                {"role": "system", "content": CONTAINS_DATA_MSG},
                {"role": "user", "content": needed_prompt},
            ],
        )

        return "true" in response["message"]["content"].lower()

    def search(self, prompt: str) -> Optional[Dict]:
        """Main search function that returns the best relevant result."""
        # Generate search query
        query = self.generate_search_query(prompt)

        # Get search results
        results = self.search_duckduckgo(query)

        # Process each result until finding relevant content
        for result in results:
            content = self.extract_content(result["link"])
            if not content:
                continue

            # Verify content relevance
            if self.verify_content_relevance(content, query, prompt):
                return {
                    "query": query,
                    "url": result["link"],
                    "content": content,
                    "description": result["search_description"],
                }

        return None


def ai_search(query):
    search_tool = AISearchTool()
    result = search_tool.search(query)
    if result:
        return result.get("content")


# Usage example:
if __name__ == "__main__":
    query = "find description of Billie Eilish lyrics style"
    res = ai_search(query)
    print(res.keys())
    print(res.get("content"))
