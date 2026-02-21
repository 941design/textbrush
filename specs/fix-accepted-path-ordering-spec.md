# Feature Specification: Fix Accepted Path Ordering to Chronological

**Status:** Planned (Not Implemented)
**Priority:** Medium
**Target Version:** TBD

## Problem Statement

The spec (spec.md:152, 505) requires:

> Paths printed in chronological order (viewing order)

The implementation in `handle_accept` (handler.py:253) orders paths by sorted backend index:

```python
images_to_accept = [
    self._image_index_map[idx]
    for idx in sorted(self._image_index_map.keys())
    if idx not in self._deleted_indices
]
```

Backend indices are assigned in generation order (monotonically increasing). "Chronological viewing order" means the order in which images were first viewed by the user, which may differ from generation order (e.g., user navigates backward to review earlier images, or images are generated out of sequence in a future multi-prompt scenario).

In the current single-generation flow, generation order and viewing order are identical (images are viewed sequentially as generated). However:

1. The spec explicitly says "viewing order," not "generation order."
2. If viewing order diverges from generation order in any future scenario, the contract breaks silently.
3. The CLI exit contract (spec.md:505) also says "chronological order (viewing order)" — this is a stable interface for scripts.

## Core Functionality

Accept images in the order they were first delivered to the frontend (viewing order), not sorted by backend index.

## Functional Requirements

### FR1: Track Delivery Order

**Requirement:** Maintain a delivery-ordered list of image indices in `MessageHandler`.

**Implementation:** The handler already maintains `_delivered_images` (a list of `BufferedImage`). However, after the backend-owned-image-list refactor, images are tracked in `_image_index_map` (a dict keyed by index) which has no inherent order.

**Required change:** Maintain a `_delivery_order: list[int]` that records the order in which images were delivered to the frontend via `IMAGE_READY` events. Each time `_start_image_delivery` sends an image, append its index to `_delivery_order`.

### FR2: Accept in Delivery Order

**Requirement:** `handle_accept` must iterate images in `_delivery_order` instead of `sorted(self._image_index_map.keys())`.

**Updated logic:**
```python
images_to_accept = [
    self._image_index_map[idx]
    for idx in self._delivery_order
    if idx in self._image_index_map and idx not in self._deleted_indices
]
```

This preserves the order in which images were presented to the user.

### FR3: Clean Up Delivery Order on Delete

**Requirement:** When an image is soft-deleted (via `handle_delete`), it is already excluded by the `not in self._deleted_indices` filter. No removal from `_delivery_order` is needed — the filter handles it.

### FR4: Clear Delivery Order on Accept

**Requirement:** `_delivery_order` must be cleared along with `_image_index_map` and `_deleted_indices` after a successful accept.

## Critical Constraints

1. **Thread safety.** `_delivery_order` must be protected by `_state_lock`, same as other state fields.
2. **No duplicates.** Each index appears in `_delivery_order` exactly once.
3. **Backward compatible.** In the current single-generation flow, delivery order equals generation order, so output order doesn't change for existing users.

## Integration Points

### Backend (`textbrush/ipc/handler.py`)
- `__init__`: Add `self._delivery_order: list[int] = []`
- `_start_image_delivery` (or wherever `IMAGE_READY` is sent): Append index to `_delivery_order`
- `handle_accept`: Use `_delivery_order` for iteration order
- Clear `_delivery_order` alongside other state in `handle_accept`

## Out of Scope

- Frontend-side reordering (the frontend displays images in its own list order; this spec only concerns the backend's ACCEPTED event path order)
- Tracking "most recently viewed" order (delivery order = first-viewed order)
- Multi-session order tracking

## Success Criteria

1. Accepted paths are emitted in the order images were delivered to the frontend.
2. In the current single-generation flow, output order is unchanged (delivery order = generation order).
3. Deleted images are excluded from the accepted paths.
4. `_delivery_order` is properly cleared after accept.
5. All existing accept tests pass.
