"""Values the hygiene audit flags that someone has checked and explained. Starts empty.

A script that loads values passes VALUE_ALLOW to data_hygiene.require_clean():

    from data_hygiene import audit, require_clean
    from value_quirks import VALUE_ALLOW
    require_clean(audit(values, "Source picklist Status"), VALUE_ALLOW)

A new flag stops the script until someone checks it and adds it here with its reason, so nothing odd is matched or
counted by accident. Each entry is the exact value as the source holds it (spaces, dashes and quotes included),
mapped to where it comes from and why it's fine. Allowing "None" covers only "None", never "none" or "None ".

Add entries only after you've looked at the value in the source. Don't add one to make a script pass.
"""

VALUE_ALLOW: dict[str, str] = {
    # Example (remove the # to use it, and replace it with your own):
    # "Pending Review ": "Trailing space in the source system's Status list; built in Salesforce as Pending Review",
}
