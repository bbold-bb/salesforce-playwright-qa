# ACME-11 Contact Channel on support requests

**Story:** As a support agent, I want to record how the customer contacted us, so the team can see which channels bring in the most cases.

## Acceptance criteria

1. A support agent can pick a Contact Channel when creating a Support Request, and it saves with the case.
2. Contact Channel offers exactly these values: Phone, Email, Chat, Web.
3. The "Cases by Contact Channel" report in Support Reports groups cases by Contact Channel, and a new case shows up under its channel.
4. The Support Agent permission set gives edit access to Contact Channel.

## Story Test Steps

- Create a Support Request with a channel and check it saved.
- Run the report and find the case under its channel.
