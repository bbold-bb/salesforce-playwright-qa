# ACME-12 Resolution Summary before closing

**Story:** As a support supervisor, I want every closed Support Request to say how it was resolved, so we can reuse fixes.

## Acceptance criteria

1. A support agent who tries to close a Support Request with Resolution Summary blank is stopped, with the message "Add a Resolution Summary before closing the case."
2. With a Resolution Summary filled in, the support agent can close the Support Request.
3. The rule applies to Support Requests only: a Billing Question closes without a Resolution Summary.

## Story Test Steps

- Try to close a case without a summary, then with one.
