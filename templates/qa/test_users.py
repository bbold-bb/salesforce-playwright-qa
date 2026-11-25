"""Creates a tester's own test users in a sandbox, one for each person they test as.

Who to test as, and the access each one holds, is in playwright/personas.json, which the whole team shares. An entry is
usually a persona (a specialist, a supervisor), but it can be anyone a story needs: a specialist with an add-on, a person
with no access. Each tester then has a set of users of their own, named for them (SpecialistTest Ana P), so two people
testing in one sandbox don't see each other's records, tabs and changes. Specs ask for the persona, testUser('Specialist'),
and get this machine's user for it.

  python3 test_users.py --org my-partial-sandbox --tester "Ana P"                    # reads only: the plan
  python3 test_users.py --org my-partial-sandbox --tester "Ana P" --rehearse         # creates, then undoes it all
  python3 test_users.py --org my-partial-sandbox --tester "Ana P" --apply            # creates, then writes the settings
  python3 test_users.py --org my-partial-sandbox --tester "Ana P" --check            # reads only: users against the file
  python3 test_users.py --org my-partial-sandbox --tester "Ana P" --write-settings   # this machine's settings only
  python3 test_users.py --org my-partial-sandbox --tester "Ana P" --rollback         # deactivates, removes access
  python3 test_users.py --org my-partial-sandbox --from-user "Some User" --as Lead   # reads only: prints an entry

--persona Specialist (repeatable) limits any of these to some of the entries.

Sandboxes and scratch orgs only. No password is set and no email is sent: QA signs in with Login As, and users are
inserted with the new user email off (a sandbox on "System email only" would otherwise let it out). Safe to rerun: what a
user already has is left alone, and what's missing is added. Access the file doesn't list is never removed; --check
reports it. Salesforce users can't be deleted, so --rollback deactivates them, and --apply later brings them back.
"""
import argparse, json, os, re, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PERSONAS = HERE / "playwright" / "personas.json"
SETTINGS = HERE / "playwright" / "test-users.local.json"
EMAIL_DOMAIN = "example.com"
APEX_LIMIT = 20000  # characters of anonymous Apex

# Access lists in an entry: key -> (object, name field, extra filter)
ACCESS = {
    "permission_set_licenses": ("PermissionSetLicense", "DeveloperName", ""),
    "permission_set_groups": ("PermissionSetGroup", "DeveloperName", ""),
    "permission_sets": ("PermissionSet", "Name", " AND IsOwnedByProfile = false AND Type != 'Group'"),
    "public_groups": ("Group", "DeveloperName", " AND Type = 'Regular'"),
    "queues": ("Group", "DeveloperName", " AND Type = 'Queue'"),
}
# User fields an entry may set under "user", on top of "defaults".
USER_FIELDS = ["TimeZoneSidKey", "LocaleSidKey", "LanguageLocaleKey", "EmailEncodingKey", "UserPermissionsKnowledgeUser",
               "UserPermissionsSupportUser", "UserPermissionsInteractionUser", "UserPermissionsMarketingUser"]
REQUIRED_FIELDS = USER_FIELDS[:4]
ENTRY_KEYS = {"description", "profile", "role", "user", *ACCESS}


class Stop(Exception):
    """Something to fix before anything is created. Its message is the whole output."""


# --- The personas file and the names -----------------------------------------------------------------------------

def load_personas(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise Stop(f"No {path}")
    except json.JSONDecodeError as e:
        raise Stop(f"{path} isn't valid JSON: {e}")
    problems = validate(data)
    if problems:
        raise Stop(f"{Path(path).name}:\n  " + "\n  ".join(problems))
    return data


def validate(data):
    """What's wrong with the personas file, by itself. Whether the org has what it names is checked against the org."""
    if not isinstance(data, dict):
        return ["the file isn't an object with \"defaults\" and \"personas\""]
    problems = []
    if set(data) - {"defaults", "personas"}:
        problems.append(f"unknown key {sorted(set(data) - {'defaults', 'personas'})}")
    defaults, personas = data.get("defaults", {}), data.get("personas")
    if not isinstance(defaults, dict):
        return problems + ["\"defaults\" isn't an object"]
    if not isinstance(personas, dict) or not personas:
        return problems + ["\"personas\" has no entries"]
    for f in set(defaults) - set(USER_FIELDS):
        problems.append(f"defaults: {f} isn't a user field this script sets ({', '.join(USER_FIELDS)})")
    for key, p in personas.items():
        if not re.fullmatch(r"[A-Z][A-Za-z0-9]{0,24}", key):
            problems.append(f"{key}: use letters and digits, starting with a capital, at most 25 (for example SpecialistSpanish)")
        if not isinstance(p, dict):
            problems.append(f"{key}: isn't an object")
            continue
        for k in sorted(set(p) - ENTRY_KEYS):
            problems.append(f"{key}: unknown key {k} (known: {', '.join(sorted(ENTRY_KEYS))})")
        for k in ("profile", "role"):
            v = p.get(k)
            if (k == "profile" or v is not None) and not clean(v):
                problems.append(f"{key}: {k} is missing, or has spaces around it")
        for k in ACCESS:
            v = p.get(k, [])
            if not isinstance(v, list) or not all(clean(x) for x in v):
                problems.append(f"{key}: {k} isn't a list of names with no spaces around them")
            elif len(set(v)) != len(v):
                problems.append(f"{key}: {k} names something twice")
        user = p.get("user", {})
        if not isinstance(user, dict):
            problems.append(f"{key}: user isn't an object")
            continue
        for f in set(user) - set(USER_FIELDS):
            problems.append(f"{key}: {f} isn't a user field this script sets ({', '.join(USER_FIELDS)})")
        fields = {**defaults, **user}
        for f in REQUIRED_FIELDS:
            if not clean(fields.get(f)):
                problems.append(f"{key}: no {f}, here or in defaults")
        for f in USER_FIELDS[4:]:
            if f in fields and not isinstance(fields[f], bool):
                problems.append(f"{key}: {f} is true or false")
    # Some checks match part of a name on screen, and "SeniorSpecialistTest Ana P" holds "SpecialistTest Ana P".
    for a in personas:
        for b in personas:
            if a != b and b.lower().endswith(a.lower()):
                problems.append(f"{b} ends with {a}, so one user's name would hold the other's: rename one (for example {a}Senior)")
    return problems


def clean(v):
    return isinstance(v, str) and bool(v) and v == v.strip() and "  " not in v


def tester_tag(tester):
    if not clean(tester):
        raise Stop("--tester is the tester's name as it should show, with no spaces around it, for example \"Ana P\"")
    tag = re.sub(r"[^a-z0-9]", "", tester.lower())
    if not tag or not tester.isascii() or not re.fullmatch(r"[A-Za-z0-9 .'-]{1,30}", tester):
        raise Stop("--tester is at most 30 plain letters, digits, spaces, full stops, apostrophes or hyphens, for example \"Ana P\"")
    return tag


def identity(key, tester, org_id):
    """One test user's own values. The org's ID is in the username because a username is unique across all of Salesforce."""
    tag = tester_tag(tester)
    base = f"{key.lower()}test.{tag}"
    username = f"{base}.{org_id.lower()}@{EMAIL_DOMAIN}"
    if len(username) > 80:
        raise Stop(f"{key}: the username {username} is over 80 characters. Use a shorter --tester or persona name")
    return {"FirstName": f"{key}Test", "LastName": tester, "Username": username, "Email": f"{base}@{EMAIL_DOMAIN}",
            "Alias": (tag[:3] + key.lower())[:8], "CommunityNickname": f"{base}.{org_id[-6:].lower()}"[:40]}


def full_name(ident):
    return f"{ident['FirstName']} {ident['LastName']}"


def name_clashes(mine, others):
    """Names that equal, hold or sit inside one of mine. mine and others are full names; others leaves mine out."""
    out = []
    for m in mine:
        for o in others:
            if m.lower() in o.lower() or o.lower() in m.lower():
                out.append(f"{m} and {o}")
    return out


def wanted_fields(data, key):
    return {**data.get("defaults", {}), **data["personas"][key].get("user", {})}


# --- The org ---------------------------------------------------------------------------------------------------------

class Org:
    def __init__(self, alias):
        self.alias = alias

    def sf(self, args):
        env = {**os.environ, "SF_DISABLE_COLORS": "true", "FORCE_COLOR": "0", "NO_COLOR": "1"}
        out = subprocess.run(["sf", *args, "-o", self.alias, "--json"], capture_output=True, text=True, env=env)
        try:
            d = json.loads(out.stdout)
        except json.JSONDecodeError:
            raise Stop(f"sf {' '.join(args[:3])}: {(out.stderr or out.stdout).strip()[:500] or 'no answer'}")
        return d

    def q(self, soql):
        d = self.sf(["data", "query", "-q", soql])
        if d.get("status") != 0:
            raise Stop(f"Query failed: {d.get('message')}\n  {soql}")
        return d["result"]["records"]

    def apex(self, code):
        with tempfile.NamedTemporaryFile("w", suffix=".apex", delete=False, encoding="utf-8") as f:
            f.write(code)
        try:
            d = self.sf(["apex", "run", "-f", f.name])
        finally:
            os.unlink(f.name)
        r = d.get("result") or d.get("data") or d
        return bool(r.get("success")), r.get("exceptionMessage") or r.get("compileProblem") or d.get("message") or ""


def soql_list(names):
    return ", ".join("'" + n.replace("\\", "\\\\").replace("'", "\\'") + "'" for n in names)


def resolve(org, data, keys):
    """The org's IDs for everything the entries name. SOQL matches text whatever its case, so names are compared exactly."""
    ids, problems = {}, []

    def find(kind, obj, field, extra, names):
        if not names:
            return
        fields = ["Id", field] + (["Status"] if obj == "PermissionSetGroup" else [])
        rows = org.q(f"SELECT {', '.join(fields)} FROM {obj} WHERE {field} IN ({soql_list(sorted(names))}){extra}")
        for n in sorted(names):
            found = [r for r in rows if r[field] == n]
            if len(found) != 1:
                near = sorted({r[field] for r in rows if r[field].lower() == n.lower() and r[field] != n})
                problems.append(f"{kind.replace('_', ' ')}: {n}: {len(found)} in the org" + (f" (it has {', '.join(near)})" if near else ""))
                continue
            if found[0].get("Status") not in (None, "Updated"):
                problems.append(f"{kind.replace('_', ' ')}: {n}: its status is {found[0]['Status']}, so wait for it to recalculate")
            ids[(kind, n)] = found[0]["Id"]

    entries = [data["personas"][k] for k in keys]
    find("profile", "Profile", "Name", "", {p["profile"] for p in entries})
    find("role", "UserRole", "DeveloperName", "", {p["role"] for p in entries if p.get("role")})
    for kind, (obj, field, extra) in ACCESS.items():
        find(kind, obj, field, extra, {n for p in entries for n in p.get(kind, [])})
    if problems:
        raise Stop("The org doesn't have what personas.json names:\n  " + "\n  ".join(problems))
    return ids


def holdings(org, user_ids):
    """What each user holds, by name, in the same lists as an entry."""
    held = {i: {k: set() for k in ACCESS} for i in user_ids}
    if not user_ids:
        return held
    ids = soql_list(user_ids)
    for r in org.q("SELECT AssigneeId, PermissionSet.Name, PermissionSetGroup.DeveloperName FROM PermissionSetAssignment "
                   f"WHERE AssigneeId IN ({ids}) AND PermissionSet.IsOwnedByProfile = false"):
        g = r.get("PermissionSetGroup")
        held[r["AssigneeId"]]["permission_set_groups" if g else "permission_sets"].add(g["DeveloperName"] if g else r["PermissionSet"]["Name"])
    for r in org.q(f"SELECT AssigneeId, PermissionSetLicense.DeveloperName FROM PermissionSetLicenseAssign WHERE AssigneeId IN ({ids})"):
        held[r["AssigneeId"]]["permission_set_licenses"].add(r["PermissionSetLicense"]["DeveloperName"])
    for r in org.q(f"SELECT UserOrGroupId, Group.DeveloperName, Group.Type FROM GroupMember WHERE UserOrGroupId IN ({ids})"):
        kind = {"Regular": "public_groups", "Queue": "queues"}.get(r["Group"]["Type"])
        if kind:
            held[r["UserOrGroupId"]][kind].add(r["Group"]["DeveloperName"])
    return held


def user_select(org):
    """The fields to read from User. Some, such as the Knowledge checkbox, exist only where the feature is on."""
    d = org.sf(["sobject", "describe", "--sobject", "User"])
    if d.get("status") != 0:
        raise Stop(f"Can't read the User object: {d.get('message')}")
    there = {f["name"] for f in d["result"]["fields"]}
    fields = [f for f in USER_FIELDS if f in there]
    return "Id, Name, FirstName, LastName, Username, Email, Alias, IsActive, Profile.Name, UserRole.DeveloperName, " + ", ".join(fields), set(fields)


def license_needs(plan, profile_license):
    """How many of each license the plan takes. plan rows: persona, profile, uses_license, add."""
    need = {}
    for p in plan:
        if p["uses_license"]:
            k = ("user license", profile_license[p["profile"]])
            need[k] = need.get(k, 0) + 1
        for n in p["add"]["permission_set_licenses"]:
            k = ("permission set license", n)
            need[k] = need.get(k, 0) + 1
    return need


def license_report(org, plan):
    """A line per license the plan takes, and the ones there aren't enough of."""
    profiles = sorted({p["profile"] for p in plan})
    rows = org.q(f"SELECT Name, UserLicense.Name, UserLicense.TotalLicenses, UserLicense.UsedLicenses FROM Profile WHERE Name IN ({soql_list(profiles)})")
    by_profile = {r["Name"]: r["UserLicense"] for r in rows}
    need = license_needs(plan, {n: l["Name"] for n, l in by_profile.items()})
    free = {("user license", l["Name"]): (l["TotalLicenses"], l["UsedLicenses"]) for l in by_profile.values()}
    psls = sorted({n for k, n in need if k == "permission set license"})
    if psls:
        for r in org.q(f"SELECT DeveloperName, TotalLicenses, UsedLicenses FROM PermissionSetLicense WHERE DeveloperName IN ({soql_list(psls)})"):
            free[("permission set license", r["DeveloperName"])] = (r["TotalLicenses"], r["UsedLicenses"])
    lines, short = [], []
    for (kind, name), n in sorted(need.items()):
        total, used = free[(kind, name)]
        left = None if total is None or total < 0 else total - used  # -1 is unlimited
        lines.append(f"{kind} {name}: needs {n}, {'unlimited' if left is None else left} free")
        if left is not None and n > left:
            short.append(f"{kind} {name}: needs {n}, {left} free")
    return lines, short


# --- What to create ----------------------------------------------------------------------------------------------------

def apex_value(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    return "'" + str(v).replace("\\", "\\\\").replace("'", "\\'") + "'"


def build_apex(plan, ids, rehearse):
    """One transaction, so it all happens or none of it does. A rehearsal ends in an exception, which undoes it."""
    body = ["List<User> us = new List<User>();", "List<User> fresh = new List<User>();", "List<User> old = new List<User>();", "User u;"]
    for p in plan:
        fields = {**p["fields"], "IsActive": True}
        if p["id"]:
            body.append(f"u = new User(Id = {apex_value(p['id'])}, {', '.join(f'{k} = {apex_value(v)}' for k, v in fields.items())});")
            body.append("us.add(u);" + (" old.add(u);" if p["changes"] else ""))
        else:
            values = {**p["identity"], **fields}
            body.append(f"u = new User({', '.join(f'{k} = {apex_value(v)}' for k, v in values.items())}); us.add(u); fresh.add(u);")
    body += ["Database.DMLOptions quiet = new Database.DMLOptions();", "quiet.EmailHeader.triggerUserEmail = false;",
             "quiet.EmailHeader.triggerOtherEmail = false;", "quiet.EmailHeader.triggerAutoResponseEmail = false;",
             "quiet.optAllOrNone = true;", "Database.update(old, quiet);", "Database.insert(fresh, quiet);"]
    make = {
        "permission_set_licenses": ("PermissionSetLicenseAssign", "AssigneeId", "PermissionSetLicenseId"),
        "permission_set_groups": ("PermissionSetAssignment", "AssigneeId", "PermissionSetGroupId"),
        "permission_sets": ("PermissionSetAssignment", "AssigneeId", "PermissionSetId"),
        "public_groups": ("GroupMember", "UserOrGroupId", "GroupId"),
        "queues": ("GroupMember", "UserOrGroupId", "GroupId"),
    }
    for i, (kind, (obj, who, what)) in enumerate(make.items()):
        rows = [(n, name) for n, p in enumerate(plan) for name in p["add"][kind]]
        if not rows:
            continue
        body.append(f"List<{obj}> l{i} = new List<{obj}>();")
        body += [f"l{i}.add(new {obj}({who} = us[{n}].Id, {what} = {apex_value(ids[(kind, name)])}));" for n, name in rows]
        body.append(f"insert l{i};")
    if rehearse:
        body.append("throw new IllegalArgumentException('REHEARSED ' + fresh.size() + ' new, ' + old.size() + ' updated');")
    code = "\n".join(body) + "\n"
    if len(code) > APEX_LIMIT:
        raise Stop(f"Too much for one transaction ({len(code)} characters of Apex). Run it for some entries at a time with --persona")
    return code


def rollback_apex(user_ids):
    ids = soql_list(user_ids)
    return (f"List<User> us = [SELECT Id FROM User WHERE Id IN ({ids}) AND Email LIKE '%@{EMAIL_DOMAIN}'];\n"
            "delete [SELECT Id FROM PermissionSetAssignment WHERE AssigneeId IN :us AND PermissionSet.IsOwnedByProfile = false];\n"
            "delete [SELECT Id FROM GroupMember WHERE UserOrGroupId IN :us];\n"
            "delete [SELECT Id FROM PermissionSetLicenseAssign WHERE AssigneeId IN :us];\n"
            "for (User u : us) u.IsActive = false;\nupdate us;\n")


def make_plan(data, keys, tester, org_id, ids, existing, held):
    """A row per entry: what's there, what changes and what's added. existing is by username, held by user ID."""
    plan = []
    for key in keys:
        p, ident = data["personas"][key], identity(key, tester, org_id)
        user = existing.get(ident["Username"])
        if user and user["LastName"] != tester:
            raise Stop(f"{ident['Username']} is already {user['Name']}'s. Pick a --tester that isn't \"{user['LastName']}\" with other spacing or punctuation")
        if user and user["Email"] != ident["Email"]:
            raise Stop(f"{user['Name']} has the email {user['Email']}, not {ident['Email']}: not one of this script's users, or its email was changed")
        fields = {**wanted_fields(data, key), "ProfileId": ids[("profile", p["profile"])]}
        if p.get("role"):
            fields["UserRoleId"] = ids[("role", p["role"])]
        has = held[user["Id"]] if user else {k: set() for k in ACCESS}
        changes = []
        if user:
            if not user["IsActive"]:
                changes.append("inactive, made active")
            if user["Profile"]["Name"] != p["profile"]:
                changes.append(f"profile {user['Profile']['Name']} to {p['profile']}")
            role = (user.get("UserRole") or {}).get("DeveloperName")
            if p.get("role") and role != p["role"]:
                changes.append(f"role {role or 'none'} to {p['role']}")
            changes += [f"{f} {user[f]} to {v}" for f, v in wanted_fields(data, key).items() if user[f] != v]
        plan.append({"key": key, "profile": p["profile"], "identity": ident, "name": full_name(ident), "id": user["Id"] if user else None,
                     "uses_license": not user or not user["IsActive"], "fields": fields, "changes": changes,
                     "add": {k: sorted(set(p.get(k, [])) - has[k]) for k in ACCESS}})
    return plan


def compare(data, key, ident, user, held):
    """(what, expected, found) for everything the file says about one entry, the user's extra access included."""
    p = data["personas"][key]
    rows = [("active", True, user["IsActive"]), ("name", full_name(ident), user["Name"]), ("email", ident["Email"], user["Email"]),
            ("alias", ident["Alias"], user["Alias"]), ("profile", p["profile"], user["Profile"]["Name"]),
            ("role", p.get("role"), (user.get("UserRole") or {}).get("DeveloperName"))]
    rows += [(f, v, user[f]) for f, v in wanted_fields(data, key).items()]
    rows += [(k.replace("_", " "), sorted(p.get(k, [])), sorted(held[k])) for k in ACCESS]
    return rows


# --- Settings ------------------------------------------------------------------------------------------------------------

def merged_settings(text, alias, users):
    """The settings file's new text: this org's entry gains or replaces users, and other orgs are left alone."""
    try:
        data = json.loads(text) if text.strip() else {}
    except json.JSONDecodeError as e:
        raise Stop(f"{SETTINGS.name} isn't valid JSON ({e}). Fix it or move it, then run --write-settings")
    data[alias] = {**data.get(alias, {}), **users}
    return json.dumps(data, indent=2) + "\n"


def write_settings(path, alias, users):
    old = path.read_text(encoding="utf-8") if path.exists() else ""
    new = merged_settings(old, alias, users)
    path.write_text(new, encoding="utf-8")
    print(f"{path.name}, {alias}: " + ", ".join(f"{k} is {v}" for k, v in users.items()))


# --- Commands --------------------------------------------------------------------------------------------------------------

def entry_from_user(org, name, key, select):
    """Prints a personas.json entry with the access an existing user holds. Nothing that names the person goes in."""
    rows = org.q(f"SELECT {select} FROM User WHERE Name = {soql_list([name])} AND IsActive = true")
    if len(rows) != 1:
        raise Stop(f"Expected one active user named {name}, found {len(rows)}")
    u, held = rows[0], holdings(org, [rows[0]["Id"]])[rows[0]["Id"]]
    entry = {"description": "", "profile": u["Profile"]["Name"]}
    if u.get("UserRole"):
        entry["role"] = u["UserRole"]["DeveloperName"]
    entry["user"] = {f: u[f] for f in USER_FIELDS if f in REQUIRED_FIELDS or u.get(f)}
    entry.update({k: sorted(v) for k, v in held.items() if v})
    print(json.dumps({key: entry}, indent=2))
    print("Read it before adding it to personas.json: leave out access this person holds and the persona shouldn't.", file=sys.stderr)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Creates a tester's own test users from playwright/personas.json. See the top of this file.")
    ap.add_argument("--org", default=os.environ.get("SF_ORG"), help="The sandbox's sf CLI alias (or set SF_ORG)")
    ap.add_argument("--tester", help="The tester's name, shown as the users' last name, for example \"Ana P\"")
    ap.add_argument("--persona", action="append", help="Only this entry of personas.json (repeatable)")
    ap.add_argument("--personas", type=Path, default=PERSONAS, help="The personas file")
    ap.add_argument("--settings", type=Path, default=SETTINGS, help="The settings file for this machine")
    ap.add_argument("--as", dest="as_key", metavar="KEY", help="With --from-user: the name for the entry")
    mode = ap.add_mutually_exclusive_group()
    for m in ("rehearse", "apply", "check", "write-settings", "rollback"):
        mode.add_argument(f"--{m}", action="store_true")
    mode.add_argument("--from-user", metavar="NAME", help="Print an entry with the access this user holds")
    a = ap.parse_args(argv)
    if not a.org:
        raise Stop("Give the sandbox's alias with --org, or set SF_ORG")
    org = Org(a.org)
    info = org.q("SELECT Id, IsSandbox FROM Organization")[0]
    if not info["IsSandbox"]:
        raise Stop(f"{a.org} isn't a sandbox or scratch org. Test users are never created anywhere else")
    if a.from_user:
        if not a.as_key:
            raise Stop("Give the entry a name with --as, for example --as Specialist")
        entry_from_user(org, a.from_user, a.as_key, user_select(org)[0])
        return 0
    if not a.tester:
        raise Stop("Give the tester's name with --tester, for example --tester \"Ana P\"")
    data = load_personas(a.personas)
    for k in a.persona or []:
        if k not in data["personas"]:
            raise Stop(f"personas.json has no {k} (it has {', '.join(data['personas'])})")
    keys = [k for k in data["personas"] if not a.persona or k in a.persona]
    select, there = user_select(org)
    missing = [f"{k}: {f}" for k in keys for f in wanted_fields(data, k) if f not in there]
    if missing:
        raise Stop("The org's users don't have these fields (the feature is off):\n  " + "\n  ".join(missing))
    idents = {k: identity(k, a.tester, info["Id"]) for k in keys}
    names = [full_name(i) for i in idents.values()]
    usernames = [i["Username"] for i in idents.values()]
    existing = {r["Username"]: r for r in org.q(f"SELECT {select} FROM User WHERE Username IN ({soql_list(usernames)})")}
    held = holdings(org, [r["Id"] for r in existing.values()])

    if a.rollback:
        mine = [r for i in idents.values() if (r := existing.get(i["Username"])) and r["Email"] == i["Email"]]
        if not mine:
            raise Stop("None of these users exist, so there's nothing to roll back")
        ok, message = org.apex(rollback_apex([r["Id"] for r in mine]))
        print(("Deactivated, access removed: " if ok else f"Rollback FAILED, nothing changed ({message}): ") + ", ".join(r["Name"] for r in mine))
        return 0 if ok else 1

    if a.check:
        wrong = 0
        for k, ident in idents.items():
            user = existing.get(ident["Username"])
            if not user:
                print(f"MISSING    {full_name(ident)}")
                wrong += 1
                continue
            for what, want, got in compare(data, k, ident, user, held[user["Id"]]):
                if want != got:
                    print(f"DIFFERENT  {user['Name']}, {what}: {got if got not in (None, []) else 'none'}, expected {want if want not in (None, []) else 'none'}")
                    wrong += 1
        print(f"{len(idents)} users checked against {a.personas.name}: " + ("all the same" if not wrong else f"{wrong} different"))
        return 1 if wrong else 0

    if a.write_settings:
        there = {k: full_name(i) for k, i in idents.items() if (existing.get(i["Username"]) or {}).get("IsActive")}
        gone = [full_name(idents[k]) for k in keys if k not in there]
        if gone:
            raise Stop(f"Not active in {a.org}: {', '.join(gone)}. Create them with --apply, or pick entries with --persona")
        write_settings(a.settings, a.org, there)
        return 0

    # Any user with exactly one of these names, and every other test user, whose names these might hold or sit inside.
    others = org.q(f"SELECT Name FROM User WHERE (Name IN ({soql_list(names)}) OR (IsActive = true AND FirstName LIKE '%Test')) "
                   f"AND Username NOT IN ({soql_list(usernames)})")
    set_names = [full_name(identity(k, a.tester, info["Id"])) for k in data["personas"]]
    clashes = name_clashes(names, [r["Name"] for r in others if r["Name"] not in set_names or r["Name"] in names])
    if clashes:
        raise Stop("One user's name would hold another's, and some checks match part of a name. Pick another --tester:\n  " + "\n  ".join(clashes))
    ids = resolve(org, data, keys)
    plan = make_plan(data, keys, a.tester, info["Id"], ids, existing, held)
    for p in plan:
        state = "new" if not p["id"] else "exists" + (": " + "; ".join(p["changes"]) if p["changes"] else "")
        print(f"{p['name']}  ({state})\n    {p['identity']['Username']}\n    profile: {p['profile']}")
        for k, v in p["add"].items():
            if v:
                print(f"    add {k.replace('_', ' ')}: {', '.join(v)}")
    lines, short = license_report(org, plan)
    for line in lines:
        print(line)
    if short:
        raise Stop("Not enough licenses. Free some, or create fewer with --persona:\n  " + "\n  ".join(short))
    if not (a.rehearse or a.apply):
        print("Plan only: nothing created. Next: --rehearse, then --apply.")
        return 0
    ok, message = org.apex(build_apex(plan, ids, a.rehearse))
    if a.rehearse:
        passed = "REHEARSED" in message
        print(("Rehearsal passed, nothing kept: " if passed else "Rehearsal FAILED, nothing kept: ") + message)
        return 0 if passed else 1
    if not ok:
        print(f"FAILED, nothing kept: {message}")
        return 1
    print("Done. Confirm with --check.")
    write_settings(a.settings, a.org, {p["key"]: p["name"] for p in plan})
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Stop as e:
        print(e, file=sys.stderr)
        sys.exit(2)
