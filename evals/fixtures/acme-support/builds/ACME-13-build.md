# ACME-13 build sub-task: Tier 2 Support queue

- Queue Tier 2 Support (`Tier_2_Support`), supported object Case, members: the Support Supervisor role.
- New picklist field on Case: Escalation Reason (`Escalation_Reason__c`), values Technical, Billing, Complaint.
- New permission set Tier 2 Access (`Tier_2_Access`): read and edit on `Escalation_Reason__c`. Assigned to Support Supervisor Test User.
