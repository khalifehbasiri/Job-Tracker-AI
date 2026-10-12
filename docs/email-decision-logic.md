# How emails become tracker updates

The importer makes two model decisions: whether an email concerns a specific application,
and which event it describes. It then extracts facts. Python decides whether those proposals
can update the tracker. Job advertisements and newsletters are outside this workflow.

## Routing rules

| Check | Result |
| --- | --- |
| No readable email body | Human review |
| Classifier refusal, incomplete response, or invalid extracted fields/dates | Human review |
| Application relevance below 0.10 | Ignore the email; no extraction call |
| Relevance at least 0.10 | Extract company, role, requisition, dates, and evidence |
| Evidence has equivalent whitespace, HTML entities, or straight/curly quotes | Locate and retain the exact corresponding excerpt in the original body |
| Evidence cannot be located | Attempt the limited local recovery described below; otherwise human review |
| Relevance below 0.90 or event confidence below 0.90 | Human review |
| Redundant confirmation or explicit routine notice for the same job within 20 minutes | Filter locally; retain source email/date and a link to its confirmation |
| Event is `other` and does not qualify for filtering | Human review; no status change is defined for this event |
| Conflicting requisition IDs or multiple identity matches | Human review |
| One application matches | Append the event to that application |
| No application matches, but both company and role are known | Create an application and append the event |
| No match and company or role is missing | Human review |

The two scores each need to reach 0.90. They are model scores, not measured accuracy guarantees.
Review reasons list confidence, unsupported event types, matching failures, and missing identity
fields rather than hiding these behind a generic confirmation message.

## Matching order

1. A thread linked to exactly one existing application, within the same mailbox account.
   Conflicting requisition IDs stop the match. A thread containing multiple applications needs review.
2. Exact company plus requisition ID across searches. Multiple candidates need review.
3. Company plus job title within the current search. An ID is optional. Formatting-normalized
   exact names are checked first, followed by a unique normalized company/title match.
   Normalization handles whitespace, HTML entities, common hyphens, company legal suffixes,
   full-stack/co-op spelling, and Sr./Senior or Jr./Junior. It preserves title word order,
   seniority, location, numbers, and language names such as C++/C#/.NET. Conflicting IDs or
   multiple candidates need review; an approximate title similarity score never decides a match.
4. Otherwise, create a new application only if both company and role are present and all
   classification/evidence checks pass. Missing information is never replaced with a guessed employer
   or role. For example, Indeed's corporate footer is not the employer in a job application.

## Recovering evidence without another AI call

Formatting validation accepts only contiguous text that maps back to an original source span.
It does not accept paraphrases, invented text, ellipses joining separate passages, or approximate
semantic matches. Failed model excerpts are retained for investigation instead of erased.

For an evidence-validation failure, local recovery can select literal event wording such as
“We received your application” or “We have not selected you to move forward.” It requires:

- Both classifier scores at least 0.90 and a supported event type.
- Explicit wording for that event in the latest body, excluding detected quoted/forwarded replies
  and appended job recommendations.
- Every proposed company, role, and requisition ID to occur in the latest body or subject.
- The normal application matching and conflict checks to pass before any update.

Recovery marks the cached result with `evidence_source = local_explicit_event`. It drops application,
deadline, and interview dates from the rejected extraction because an event excerpt does not prove
them. A recovered confirmation may use its received date under the existing date fallback.
Refusals and invalid/incomplete extractions are not repaired this way.

The Review inbox's **Recheck saved emails** button applies these rules to pending reviews using
cached emails. It makes no mailbox requests or AI calls. It checks current matches again, preserves
unresolved identity conflicts, accepts successful reviews, and updates history counts. Running it
again does not duplicate events. Overlapping user-started scans can also reuse eligible reviews.

## What an automatic update changes

A prior application confirmation or existing record is not required. When a supported email
passes the classification/evidence checks, identifies both company and role, and has no matching
application or identity conflict, the importer creates a new record and applies that email's event
in the same transaction. This also applies when rechecking eligible saved reviews.

| First known email | New record's stage | New record's outcome |
| --- | --- | --- |
| Application confirmation | Applied | Active |
| Rejection | Applied | Rejected |
| Online assessment | Assessment | Active |
| Interview | Interview | Active |
| Job offer | Offer | Active |

Stage and outcome are separate fields: a rejection is represented by the Rejected outcome.
Only a confirmation supplies the application date; other first events leave it unknown.

- Confirmation: establishes Applied status and fills a blank application date from an extracted
  date, or the confirmation's received date in UTC.
- Assessment, interview, offer: advance the stage without regressing a later stage.
- Rejection: sets the outcome to Rejected. A rejection alone does not establish an application date.
- Terminal outcomes remain terminal; only explicit manual changes can reopen them.
- Older email events cannot overwrite a newer status. Manual status overrides remain protected.
- Valid deadline/interview timestamps can create tasks; duplicate reminder tasks are not recreated.

The history counter **processed** includes ignored unrelated emails, filtered siblings, and applied updates.
It is not the number of applications created or updated.

## Filtering emails for the same application

After classification and extraction, an accepted application confirmation anchors a fixed
20-minute window in the same mailbox and search. Both classifier scores must be at least 0.90.
Company/title matching uses the rules above; matching timestamps alone never proves identity.
Filtered emails do not create events or extend the window. For example, confirmations at
12:00 and 12:19 are grouped, but another at 12:38 is retained.

- A repeated confirmation must match the same record, have valid source evidence and supported
  identity fields, and contain no new application date, deadline, interview time, or required action.
- A routine `other` email must explicitly concern privacy, email preferences, a created candidate
  account, or an application-viewed notice in its subject or opening line. A footer link is insufficient.
  Required actions, verification, incomplete applications, and status changes remain eligible for review.
- A notice without a title can use its supported company only when exactly one application with a
  confirmation is in the window. Multiple matches or conflicting IDs remain in review.
- Rejection, assessment, interview, and offer emails are retained even when received seconds apart.

Filtering removes redundant tracker work without deleting anything in Gmail/Outlook. The original
body, received date, cached extraction, representative message ID, and filter reason remain in SQLite.
History shows filtered counts. Saved reviews can be filtered without another paid API call. Imports
recheck pending reviews after processing so a later confirmation can identify an earlier notice.
This filter runs after model extraction; it does not promise to save the initial classification cost.

## Email dates on records

Gmail's `internalDate` and Outlook's `receivedDateTime` supply the source timestamp. It is normalized
to UTC, independent of model output. Every accepted or filtered email updates the record's earliest
and latest received dates, including imports processed out of order. Application details and Excel
exports show both dates. Existing linked events backfill these fields during database migration.

The **Applied on** date stays separate: a confirmation fills a blank date with its explicit extracted
submission date, otherwise its UTC received date. Existing dates are preserved. A first rejection,
assessment, interview, or offer stores its email date and status without inventing a submission date.

## Complete email content

Gmail messages can have plain-text and HTML alternatives. Some messages contain only a short
heading and footer in plain text while the HTML contains the actual application decision.
The importer prefers plain text for equivalent alternatives, but chooses stripped HTML when
plain text has at most 20 informative words and HTML supplies at least 10 additional words.
Footer text and tracking URLs are excluded from this comparison. Attachments remain excluded,
and scripts/styles are not included in the stripped body. Declared MIME character encodings
are respected so names and text in other languages are not unnecessarily corrupted.

Cached classifications describe the body originally analyzed. Fixing MIME selection does not
reclassify old cached results; those affected emails need to be fetched and analyzed again.

Implementation: [classification/extraction](../src/job_tracker/ai.py),
[source evidence and local recovery](../src/job_tracker/evidence.py),
[routing and matching](../src/job_tracker/worker.py), and
[event/status projection](../src/job_tracker/services.py).
