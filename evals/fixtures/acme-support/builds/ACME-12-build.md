# ACME-12 build sub-task: Resolution Summary rule

- New long text field on Case: Resolution Summary (`Resolution_Summary__c`), on the Support Request page in the Resolution section.
- Validation rule `Resolution_Summary_Required` on Case, active:
  `AND(RecordType.DeveloperName = 'Support_Request', ISPICKVAL(Status, 'Closed'), ISBLANK(Resolution_Summary__c))`
  Message: "Add a Resolution Summary before closing the case." Shown on the Resolution Summary field.
- Support Agent permission set: read and edit on `Resolution_Summary__c`.
