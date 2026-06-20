from __future__ import annotations

from typing import Any

DEFAULT_RAG_TEMPLATE = """### Task:
Respond to the user query using the provided context, incorporating inline citations in the format [id] **only when the <source> tag includes an explicit id attribute** (e.g., <source id="1">).

### Guidelines:
- If you don't know the answer, clearly state that.
- If uncertain, ask the user for clarification.
- Respond in the same language as the user's query.
- If the context is unreadable or of poor quality, inform the user and provide the best possible answer.
- If the answer isn't present in the context but you possess the knowledge, explain this to the user and provide the answer using your own understanding.
- **Only include inline citations using [id] (e.g., [1], [2]) when the <source> tag includes an id attribute.**
- Do not cite if the <source> tag does not contain an id attribute.
- Do not use XML tags in your response.
- Ensure citations are concise and directly related to the information provided.

### Example of Citation:
If the user asks about a specific topic and the information is found in a source with a provided id attribute, the response should include the citation like in the following example:
* "According to the study, the proposed method increases efficiency by 20% [1]."

### Output:
Provide a clear and direct response to the user's query, including inline citations in the format [id] only when the <source> tag with id attribute is present in the context.

<context>
{{CONTEXT}}
</context>
"""


def rag_template(template: str, context: str, query: str) -> str:
	body = template.strip() or DEFAULT_RAG_TEMPLATE
	body = body.replace("{{CONTEXT}}", context).replace("[context]", context)
	body = body.replace("{{QUERY}}", query).replace("[query]", query)
	return body


def sources_to_context_string(sources: list[dict[str, Any]]) -> str:
	context_string = ""
	citation_idx_map: dict[str, int] = {}
	for source in sources:
		if not isinstance(source, dict):
			continue
		documents = source.get("document") or []
		metadatas = source.get("metadata") or []
		src_info = source.get("source") or {}
		if not isinstance(documents, list):
			continue
		for index, document_text in enumerate(documents):
			metadata = metadatas[index] if index < len(metadatas) and isinstance(metadatas, list) else {}
			source_name = src_info.get("name") if isinstance(src_info, dict) else None
			source_id = "N/A"
			if isinstance(metadata, dict) and metadata.get("source"):
				source_id = str(metadata.get("source"))
			elif isinstance(src_info, dict) and src_info.get("id"):
				source_id = str(src_info.get("id"))
			if source_id not in citation_idx_map:
				citation_idx_map[source_id] = len(citation_idx_map) + 1
			name_attr = f' name="{source_name}"' if source_name else ""
			context_string += (
				f'<source id="{citation_idx_map[source_id]}"{name_attr}>{document_text}</source>\n'
			)
	return context_string.strip()
