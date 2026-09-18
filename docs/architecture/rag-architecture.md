# RAG Architecture Diagram

| Field  | Value                                   |
| ------ | --------------------------------------- |
| Week   | 3                                       |
| Owner  | Jim                                     |
| Due    | 18 September 2026                       |
| Status | Completed                               |
| Path   | `docs/architecture/rag-architecture.md` |

## Brief requirement

![](./RAG_ARCHITECTURE.png)

## Write-up

The RAG architecture is used to retrieve relevant procurement policy clauses from the controlled Policy Corpus and ground the model's response in those retrieved sources.

The process is divided into three stages.

### 1. Offline / Corpus Preparation

Versioned procurement policy documents are loaded from the Policy Corpus. The documents are split into smaller chunks, with metadata attached to each chunk, including the document name, document version, and clause identifier.

Each chunk is then converted into an embedding and stored in a vector index. The original policy documents remain the source of truth, while the vector index is used only to support retrieval.

### 2. Runtime Retrieval

When the Procurement Officer confirms the landed-cost comparison, the system uses the current requisition context, including the item name, category, and landed cost, to build a retrieval query.

The query is converted into an embedding and compared against the vector index. The most relevant policy chunks are returned as retrieval results.

If no relevant clause is found, the system explicitly reports that no matching policy clause was found rather than generating or inventing one.

### 3. Grounded Generation and Review

The retrieved policy chunks are combined with the requisition context and placed into the model prompt. Gemini then uses this supplied context to identify and explain the relevant procurement policy.

The model is expected to use only the retrieved policy evidence for policy claims. The generated result is passed through a citation validation step that checks the referenced document name, version, and clause identifier against the Policy Corpus.

If validation succeeds, the result is shown to the Procurement Officer for review before the workflow continues to justification drafting.

If policy retrieval or citation validation fails, the workflow pauses, preserves its current state, and allows the operation to be retried.

### Source Grounding

Every policy claim produced by the AI must be traceable to a retrieved clause from the controlled Policy Corpus. The system therefore retains source metadata such as:

- document name;
- document version;
- clause identifier.

This allows the Procurement Officer to verify the source of the policy information before it is used in the requisition justification.
