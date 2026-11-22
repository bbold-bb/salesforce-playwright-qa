# ACME-11 build sub-task: Contact Channel

- New picklist field on Case: Contact Channel (`Contact_Channel__c`), restricted, values Phone, Email, Chat, Web. Not required.
- Added to the Support Request page layout and the Lightning record page, in the Case Details section.
- Support Agent permission set: read and edit on `Contact_Channel__c`.
- New report "Cases by Contact Channel" (`Cases_by_Contact_Channel`) in Support Reports, grouped by Contact Channel, all time.
