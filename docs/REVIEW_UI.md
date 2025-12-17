# Review UI Specification

The Review UI enables analysts to verify, correct, and approve extracted data before publication to Allocator Pro.

---

## Design Principles

1. **Evidence-first:** Always show source alongside extraction
2. **Minimal friction:** One-click approval for correct extractions
3. **Auditable:** Every edit is logged with reason
4. **Efficient:** Triage by priority, batch similar items

---

## User Roles

| Role | Permissions |
|------|-------------|
| Analyst | View, edit, approve, reject documents |
| Senior Analyst | All analyst + override confidence routing |
| Admin | All + manage queues, adjust thresholds |

---

## Queue Structure

### Must-Review Queue

- Documents with `analyst_attention_required = true`
- LOW confidence band
- Priority: Oldest first (FIFO)

### Spot-Check Queue

- Sampled MEDIUM confidence documents
- Priority: Random (to avoid bias)

### Escalation Queue

- Documents flagged by analysts for senior review
- Priority: Escalation time (oldest first)

---

## Review Interface Layout

```
┌────────────────────────────────────────────────────────────────────────────┐
│  [Markets Recon] Review Queue                    [Queue: Must-Review (23)] │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  ┌─────────────────────────────┐  ┌─────────────────────────────────────┐  │
│  │                             │  │                                     │  │
│  │      PDF VIEWER             │  │      EXTRACTION PANEL               │  │
│  │                             │  │                                     │  │
│  │  [Page navigation]          │  │  Document Profile                   │  │
│  │                             │  │  ├─ Manager: BlackRock [✓]          │  │
│  │  ┌───────────────────────┐  │  │  ├─ Date: 2025-07-15 [✓]           │  │
│  │  │                       │  │  │  └─ Type: MID_YEAR_OUTLOOK [✓]     │  │
│  │  │   PDF PAGE            │  │  │                                     │  │
│  │  │   (with highlights)   │  │  │  Allocation Calls (3)               │  │
│  │  │                       │  │  │  ┌─────────────────────────────────┐│  │
│  │  │                       │  │  │  │ [!] German Bunds: OVERWEIGHT    ││  │
│  │  │                       │  │  │  │     Evidence: p.4               ││  │
│  │  │                       │  │  │  │     Confidence: 0.72            ││  │
│  │  │                       │  │  │  │     [Edit] [Approve] [Reject]   ││  │
│  │  └───────────────────────┘  │  │  └─────────────────────────────────┘│  │
│  │                             │  │  ┌─────────────────────────────────┐│  │
│  │  [◀ Prev] [Page 4/12] [▶]   │  │  │ [✓] US Treasuries: NEUTRAL     ││  │
│  │                             │  │  │     Evidence: p.6               ││  │
│  └─────────────────────────────┘  │  │     Confidence: 0.85            ││  │
│                                   │  └─────────────────────────────────┘│  │
│                                   │                                     │  │
│                                   │  [Approve All] [Skip] [Escalate]    │  │
│                                   └─────────────────────────────────────┘  │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## PDF Viewer Component

### Features

- **Page navigation:** Jump to any page, keyboard shortcuts
- **Evidence highlighting:** Yellow highlight on cited text
- **Click-to-cite:** Click text to add as new citation
- **Zoom controls:** Fit width, fit page, zoom in/out
- **Search:** Find text in document

### Highlighting Logic

```typescript
interface BoundingBox {
  // Normalized 0-1 coordinates on the page
  x0: number;
  y0: number;
  x1: number;
  y1: number;
}

interface EvidenceHighlight {
  callId: string;
  page: number;
  bboxes: BoundingBox[];
}

interface HighlightConfig {
  // Derived from core `Citation.block_ids` by looking up `DocumentBlock.bbox`.
  highlights: EvidenceHighlight[];
  activeCallId: string | null;
  highlightColor: {
    active: "#FFE066",    // Currently selected call's evidence
    inactive: "#E0E0E0",  // Other calls' evidence
  };
}

function buildHighlights(
  citationsByCallId: Record<string, Citation[]>,
  blocksById: Record<string, DocumentBlock>,
): EvidenceHighlight[] {
  const highlights: EvidenceHighlight[] = [];

  for (const [callId, citations] of Object.entries(citationsByCallId)) {
    for (const citation of citations) {
      const bboxes = (citation.block_ids ?? [])
        .map((blockId) => blocksById[blockId]?.bbox)
        .filter((bbox): bbox is BoundingBox => Boolean(bbox));

      if (bboxes.length === 0) continue;

      highlights.push({ callId, page: citation.page, bboxes });
    }
  }

  return highlights;
}

function renderHighlights(page: PDFPage, config: HighlightConfig) {
  for (const highlight of config.highlights) {
    if (highlight.page !== page.number) continue;
    
    const isActive = highlight.callId === config.activeCallId;
    const color = isActive 
      ? config.highlightColor.active 
      : config.highlightColor.inactive;
    
    for (const bbox of highlight.bboxes) {
      // Render highlight box
      drawHighlight(page, bbox, color);
      
      // Add click handler to jump to extraction
      addClickHandler(bbox, () => scrollToCall(highlight.callId));
    }
  }
}
```

---

## Extraction Panel Components

### Document Profile Card

```typescript
interface ProfileCard {
  fields: {
    name: string;
    value: string;
    confidence: number;
    citations: Citation[];
    editable: boolean;
    status: "verified" | "uncertain" | "edited";
  }[];
}

// Example
{
  fields: [
    {
      name: "Manager",
      value: "BlackRock",
      confidence: 0.92,
      citations: [{chunk_id: "doc_0", block_ids: ["1_3"], page: 1}],
      editable: true,
      status: "verified"
    },
    {
      name: "Publication Date",
      value: "2025-07-15",
      confidence: 0.88,
      citations: [{chunk_id: "doc_0", block_ids: ["1_5"], page: 1}],
      editable: true,
      status: "verified"
    }
  ]
}
```

### Allocation Call Card

```typescript
interface CallCard {
  id: string;
  assetClassCategory: string;
  subAssetClass: string;
  call: "OVERWEIGHT" | "NEUTRAL" | "UNDERWEIGHT" | "UNCERTAIN";
  conviction: "HIGH" | "MEDIUM" | "LOW" | null;
  confidence: number;
  needsReview: boolean;
  reviewReason: string | null;
  rationale: string[];
  citations: Citation[];
  tooltip: string;
  
  // Edit state
  isEditing: boolean;
  editedCall: string | null;
  editReason: string | null;
}
```

### Call Card States

| State | Visual | Actions |
|-------|--------|---------|
| Verified (high confidence) | Green checkmark | Approve, Edit |
| Uncertain (needs review) | Yellow warning | Edit, Approve, Reject |
| Edited | Blue pencil | Undo, Save |
| Rejected | Red X | Restore |

---

## Edit Workflows

### Edit Call Direction

```typescript
interface EditCallFlow {
  // 1. User clicks Edit on call card
  onEditClick: () => {
    setEditMode(true);
    showCallDirectionDropdown();
  };
  
  // 2. User selects new direction
  onDirectionSelect: (newDirection: CallDirection) => {
    setEditedCall(newDirection);
    showReasonInput();  // Require reason for audit
  };
  
  // 3. User provides reason
  onReasonSubmit: (reason: string) => {
    saveEdit({
      callId,
      field: "call",
      oldValue: originalCall,
      newValue: editedCall,
      reason,
      reviewerId: currentUser.id,
      timestamp: now()
    });
    setEditMode(false);
  };
}
```

### Edit Rationale

```typescript
interface EditRationaleFlow {
  // User can:
  // - Edit existing bullets
  // - Add new bullets
  // - Remove bullets
  // - Reorder bullets
  
  // All changes tracked
  onRationaleChange: (bullets: string[]) => {
    saveEdit({
      callId,
      field: "rationale_bullets",
      oldValue: originalBullets,
      newValue: bullets,
      reason: "Analyst correction",
      reviewerId: currentUser.id,
      timestamp: now()
    });
  };
}
```

### Add Missing Call

```typescript
interface AddCallFlow {
  // 1. User clicks "Add Call"
  onAddClick: () => {
    showAssetClassPicker();  // Taxonomy dropdown
  };
  
  // 2. User selects asset class
  onAssetSelect: (category: string, subAsset: string) => {
    showCallDirectionPicker();
  };
  
  // 3. User selects direction
  onDirectionSelect: (direction: CallDirection) => {
    showCitationPicker();  // User clicks on PDF to cite
  };
  
  // 4. User cites evidence
  onCitationAdd: (citation: Citation) => {
    showRationaleInput();
  };
  
  // 5. User adds rationale
  onRationaleSubmit: (rationale: string[]) => {
    createNewCall({
      assetClassCategory: selectedCategory,
      subAssetClass: selectedSubAsset,
      call: selectedDirection,
      rationale,
      citations: [selectedCitation],
      addedByAnalyst: true,
      reviewerId: currentUser.id
    });
  };
}
```

### Mark "Not in Document"

```typescript
interface MarkAbsentFlow {
  // For extracted calls that don't exist in source
  onMarkAbsent: (callId: string) => {
    showConfirmDialog("This call was not found in the document?");
  };
  
  onConfirm: (callId: string) => {
    saveEdit({
      callId,
      action: "MARKED_ABSENT",
      reason: "Call not present in source document",
      reviewerId: currentUser.id,
      timestamp: now()
    });
    hideCall(callId);  // Remove from display
  };
}
```

---

## Approval Workflow

### Single Call Approval

```typescript
function approveCall(callId: string) {
  // Mark call as reviewed
  updateCall(callId, {
    status: "APPROVED",
    reviewedAt: now(),
    reviewedBy: currentUser.id
  });
  
  // Check if all calls approved
  if (allCallsApproved(documentId)) {
    showApproveDocumentPrompt();
  }
}
```

### Bulk Approval

```typescript
function approveAllCalls(documentId: string) {
  const calls = getCalls(documentId);
  
  // Only allow if no calls need review
  const needsReview = calls.filter(c => c.needsReview && !c.status);
  if (needsReview.length > 0) {
    showWarning(`${needsReview.length} calls still need review`);
    return;
  }
  
  // Approve all
  for (const call of calls) {
    approveCall(call.id);
  }
  
  // Approve document
  approveDocument(documentId);
}
```

### Document Approval

```typescript
function approveDocument(documentId: string) {
  // Validate all required fields reviewed
  const validation = validateForApproval(documentId);
  if (!validation.valid) {
    showError(validation.errors);
    return;
  }
  
  // Update document status
  updateDocument(documentId, {
    status: "PUBLISHED",
    publishedAt: now(),
    publishedBy: currentUser.id
  });
  
  // Publish to Allocator Pro
  publishToAllocatorPro(documentId);
  
  // Index for search
  indexForSearch(documentId);
  
  // Move to next document in queue
  loadNextDocument();
}
```

---

## Audit Log

Every action is logged:

```typescript
interface AuditEntry {
  id: string;
  documentId: string;
  callId: string | null;
  userId: string;
  action: AuditAction;
  field: string | null;
  oldValue: any;
  newValue: any;
  reason: string | null;
  timestamp: Date;
}

type AuditAction = 
  | "VIEWED"
  | "EDITED"
  | "APPROVED"
  | "REJECTED"
  | "ESCALATED"
  | "CALL_ADDED"
  | "CALL_REMOVED"
  | "MARKED_ABSENT";
```

### Audit Log Display

```
┌──────────────────────────────────────────────────────────────────┐
│ Audit Log - Document: doc_123                                    │
├──────────────────────────────────────────────────────────────────┤
│ 2025-07-20 14:32:15  analyst@firm.com  EDITED                   │
│   Call: German Bunds                                             │
│   Field: call                                                    │
│   Old: NEUTRAL  →  New: OVERWEIGHT                              │
│   Reason: "Evidence clearly states overweight preference"        │
├──────────────────────────────────────────────────────────────────┤
│ 2025-07-20 14:31:42  analyst@firm.com  VIEWED                   │
├──────────────────────────────────────────────────────────────────┤
│ 2025-07-20 10:15:00  system  CREATED                            │
│   Initial extraction with confidence 0.72                        │
└──────────────────────────────────────────────────────────────────┘
```

---

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `A` | Approve current call |
| `E` | Edit current call |
| `R` | Reject current call |
| `N` | Next call |
| `P` | Previous call |
| `Shift+A` | Approve all calls |
| `Shift+N` | Next document |
| `Ctrl+F` | Search in PDF |
| `1-9` | Jump to page |
| `Esc` | Cancel edit |

---

## Queue Management (Admin)

### Queue Dashboard

```
┌──────────────────────────────────────────────────────────────────┐
│ Queue Dashboard                                                  │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Must-Review Queue      [23 documents]                          │
│  ├─ Oldest: 2 hours ago                                         │
│  ├─ Avg. review time: 4.2 min                                   │
│  └─ [View Queue]                                                │
│                                                                  │
│  Spot-Check Queue       [8 documents]                           │
│  ├─ Oldest: 45 min ago                                          │
│  ├─ Sample rate: 20%                                            │
│  └─ [View Queue]                                                │
│                                                                  │
│  Escalation Queue       [2 documents]                           │
│  ├─ Oldest: 1 day ago                                           │
│  └─ [View Queue]                                                │
│                                                                  │
│  Today's Stats                                                   │
│  ├─ Processed: 47 documents                                     │
│  ├─ Approved: 42 (89%)                                          │
│  ├─ Edited: 31 (66%)                                            │
│  └─ Rejected: 5 (11%)                                           │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### Reassignment

```typescript
function reassignDocument(documentId: string, toUserId: string) {
  // Only admins can reassign
  requireRole("admin");
  
  updateDocument(documentId, {
    assignedTo: toUserId,
    reassignedAt: now(),
    reassignedBy: currentUser.id
  });
  
  notifyUser(toUserId, `Document assigned to you: ${documentId}`);
}
```

---

## Feedback Loop

### Analyst Feedback on Extraction Quality

```typescript
interface ExtractionFeedback {
  documentId: string;
  feedbackType: 
    | "GOOD_EXTRACTION"
    | "POOR_OCR"
    | "WRONG_TAXONOMY"
    | "MISSING_CALLS"
    | "HALLUCINATED_CONTENT"
    | "OTHER";
  details: string;
  suggestedImprovement: string | null;
}

function submitFeedback(feedback: ExtractionFeedback) {
  saveFeedback(feedback);
  
  // Auto-tag for pipeline improvement
  if (feedback.feedbackType === "WRONG_TAXONOMY") {
    flagForTaxonomyReview(feedback.documentId);
  }
  
  if (feedback.feedbackType === "HALLUCINATED_CONTENT") {
    flagForPromptReview(feedback.documentId);
  }
}
```

### Correction Aggregation

Weekly report for pipeline improvement:

```
┌──────────────────────────────────────────────────────────────────┐
│ Weekly Correction Report                                         │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Call Direction Corrections                                      │
│  ├─ Total: 47                                                   │
│  ├─ OW→N: 12, OW→UW: 3, N→OW: 18, N→UW: 8, UW→N: 4, UW→OW: 2   │
│  └─ Most corrected asset: Euro Govt Bonds (8)                   │
│                                                                  │
│  Taxonomy Mapping Issues                                         │
│  ├─ "Bunds" → GERMAN_BUNDS (correct): 15                        │
│  ├─ "European duration" → UNMAPPED: 7 (needs taxonomy update)   │
│  └─ "Credit" ambiguous (HY vs IG): 5                            │
│                                                                  │
│  Missing Calls Added by Analysts                                 │
│  ├─ Total: 23                                                   │
│  ├─ Most common category: FI_HY (8)                             │
│  └─ Avg. confidence of missed calls: 0.45                       │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```
