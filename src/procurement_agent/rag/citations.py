"""Citation validation (RAG stage 3, second half).

The architecture's citation validator: "checks that the referenced document,
version and clause ID are valid before the result is shown to the Procurement
Officer". This is what makes the answer *grounded* rather than merely plausible.

Valid means retrieved, not merely real
--------------------------------------
The AI Boundary Matrix asks that every cited clause exist in the corpus at the
cited version. This checks something stricter: that it was among the clauses
the model was actually given. A real clause the model was not shown is still an
ungrounded citation. The model would be recalling policy rather than reading
it, and nothing in its context supports what it claims the clause says. Every
retrieved clause came from the verified corpus, so passing this check also
satisfies the matrix.

The summary is checked as well as the list
------------------------------------------
Constrained decoding makes `applicable_clauses` well formed, but the summary is
free text and can name a clause, or a whole document, that the list omits:
"as required by POL-009-C02". Every identifier mentioned there must also have
been retrieved. It need not be cited as applicable, because explaining that a
supplied clause does *not* apply ("POL-001-C03 covers larger purchases") is
correct and useful.

All problems are reported, not only the first, so a trace shows everything
that was wrong with an answer in one place.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .corpus import Clause
from .grounding import GroundedAnswer
from .retriever import RetrievalResult

PROBLEM_NOT_RETRIEVED = "not_retrieved"
PROBLEM_SOURCE_MISMATCH = "source_mismatch"
PROBLEM_VERSION_MISMATCH = "version_mismatch"
PROBLEM_UNRETRIEVED_MENTION = "unretrieved_mention"

# The corpus identifier shapes: POL-001 for a document, POL-001-C02 for a
# clause. Three digits, so "COVID-19" and "ISO-9001" are not mistaken for
# references. The document pattern refuses a match that is really the start of
# a clause identifier.
_CLAUSE_MENTION = re.compile(r"\b[A-Z]{2,5}-\d{3}-C\d+\b")
_DOCUMENT_MENTION = re.compile(r"\b[A-Z]{2,5}-\d{3}\b(?!-C\d)")


@dataclass(frozen=True)
class CitationProblem:
    kind: str
    reference: str
    detail: str


@dataclass(frozen=True)
class CitationReport:
    """The verdict, what was wrong, and the cited clauses resolved for display."""

    problems: tuple[CitationProblem, ...]
    cited_clauses: tuple[Clause, ...]

    @property
    def valid(self) -> bool:
        return not self.problems


def validate_citations(answer: GroundedAnswer, retrieval: RetrievalResult) -> CitationReport:
    """Check every citation and every identifier in the summary against retrieval."""
    sent = {hit.clause.clause_id: hit.clause for hit in retrieval.clauses}
    sent_documents = {clause.source_id for clause in sent.values()}

    problems: list[CitationProblem] = []
    cited: list[Clause] = []

    for citation in answer.citations:
        clause = sent.get(citation.clause_id)
        if clause is None:
            problems.append(CitationProblem(
                PROBLEM_NOT_RETRIEVED,
                citation.clause_id,
                f"{citation.clause_id} was cited but was not among the clauses supplied",
            ))
            continue

        consistent = True
        if citation.source_id != clause.source_id:
            consistent = False
            problems.append(CitationProblem(
                PROBLEM_SOURCE_MISMATCH,
                citation.clause_id,
                f"{citation.clause_id} belongs to {clause.source_id}, "
                f"but was cited as {citation.source_id}",
            ))
        if citation.version != clause.version:
            consistent = False
            problems.append(CitationProblem(
                PROBLEM_VERSION_MISMATCH,
                citation.clause_id,
                f"{citation.clause_id} was supplied at version {clause.version}, "
                f"but was cited as version {citation.version}",
            ))
        if consistent and clause not in cited:
            cited.append(clause)

    for mention in sorted(set(_CLAUSE_MENTION.findall(answer.summary))):
        if mention not in sent:
            problems.append(CitationProblem(
                PROBLEM_UNRETRIEVED_MENTION,
                mention,
                f"the summary names {mention}, which was not among the clauses supplied",
            ))
    for mention in sorted(set(_DOCUMENT_MENTION.findall(answer.summary))):
        if mention not in sent_documents:
            problems.append(CitationProblem(
                PROBLEM_UNRETRIEVED_MENTION,
                mention,
                f"the summary names document {mention}, from which no clause was supplied",
            ))

    return CitationReport(problems=tuple(problems), cited_clauses=tuple(cited))
