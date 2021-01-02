#! /usr/bin/env python3
import collections
import datetime
import pprint
import re
import urllib.parse
import uuid

import voluptuous as v
import pymongo
import bson

s_old_story_base = v.Schema({
            "_id": bson.objectid.ObjectId,
            "id": str,
            "url": v.Url(),
            "title": str,
            "scraped": v.Any(datetime.datetime, None),
            "metadata": dict,
            "created_at": datetime.datetime,
            "publication_date": v.Any(datetime.datetime, None),
            }, required=True)
s_old_story = v.Any(
        s_old_story_base.extend({
            "metadata": {},
            "closedAt": v.Any(datetime.datetime, None),
            "closedMessage": None,
            "settings": dict,
            "tags": [],
            "type": "assets",
            "updated_at": datetime.datetime,
            "author": str,
            "description": str,
            "image": v.Url(),
            "modified_date": None,
            "section": str,
            }, required=True),
        s_old_story_base.extend({
            "metadata": v.Schema({"source": "wpimport"}, required=True),
            }),
        )

s_old_user_import = v.Schema({
    "_id": bson.objectid.ObjectId,
    "id": str,
    "username": str,
    "lowercaseUsername": str,
    "profiles": [v.Schema({
        "provider": "disqus",
        "id": str,
        }, required=True)],
    "metadata": v.Schema({"source": "wpimport", v.Optional("trust"): dict}, required=True),
    "created_at": datetime.datetime,
    v.Optional("updated_at"): datetime.datetime,
    v.Optional("action_counts"): dict, # can skip importing this I think
    }, required=True)
s_old_user_organic = v.Schema({
    "_id": bson.objectid.ObjectId,
    "status": v.Schema({
        "username": v.Schema({
            "status": v.Any("SET", "UNSET", "APPROVED"),
            "history": [v.Schema({
                "assigned_by": v.Any(None, str),
                "_id": bson.objectid.ObjectId,
                "status": v.Any("SET", "UNSET", "REJECTED", "CHANGED", "APPROVED"),
                "created_at": datetime.datetime,
                }, required=True)],
            }, required=True),
        "banned": v.Schema({
            "status": bool,
            "history": [v.Schema({
                "assigned_by": str,
                "message": str,
                "_id": bson.objectid.ObjectId,
                "status": bool,
                "created_at": datetime.datetime,
                }, required=True)],
            }, required=True),
        "suspension": v.Schema({
            "until": None,
            "history": [],
            }, required=True),
        "alwaysPremod": v.Schema({
            "status": bool,
            "history": [v.Schema({
                "assigned_by": str,
                "_id": bson.objectid.ObjectId,
                "status": bool,
                "created_at": datetime.datetime,
                }, required=True)],
            }, required=True),
        }, required=True),
    "role": v.Any("ADMIN", "STAFF", "COMMENTER", "MODERATOR"),
    "ignoresUsers": [str],
    "username": str,
    "lowercaseUsername": str,
    v.Optional("password"): str,
    "profiles": [v.Any(
        v.Schema({
            "id": str,
            "provider": v.Any("google", "facebook"),
            }, required=True),
        v.Schema({
            "id": str,
            "provider": "local",
            v.Optional("metadata"): v.Schema({
                "confirmed_at": datetime.datetime,
                "recaptcha_required": bool,
                }, required=False),
            }, required=True),
        )],
    "id": str,
    "tokens": [],
    "tags": [],
    "created_at": datetime.datetime,
    "updated_at": datetime.datetime,
    "__v": int, # version
    v.Optional("metadata"): v.Schema({
        "avatar": v.Any(v.Url(), '', re.compile(r"data:").match),
        "lastAccountDownload": datetime.datetime,
        "notifications": {
            "settings": {
                "onReply": bool,
                "onFeatured": bool,
                "digestFrequency": v.Any("HOURLY", "DAILY", "NONE"),
                },
            "digests": [dict], # only a couple of users have this set - I think it's for buffering notifs, so can ignore
            },
        "trust": {
            "comment": {"karma": int},
            "flag": {"karma": int},
            },
        "scheduledDeletionDate": datetime.datetime, # best to handle this at import time I think
        }, required=False),
    v.Optional("action_counts"): dict, # can skip importing this I think
    }, required=True)
s_old_user = v.Any(s_old_user_organic, s_old_user_import)

s_old_comment_base = v.Schema({
    "_id": bson.objectid.ObjectId,
    "status": v.Any("ACCEPTED", "REJECTED", "NONE"),
    v.Optional("status_history"): [v.Schema({
        "assigned_by": v.Any(None, str),
        "type": v.Any("ACCEPTED", "NONE", "REJECTED", "SYSTEM_WITHHELD"),
        "created_at": datetime.datetime,
        }, required=True)],
    "id": str,
    "author_id": str,
    "parent_id": v.Any(None, str),
    "created_at": datetime.datetime,
    "updated_at": datetime.datetime,
    "asset_id": str,
    "body": str,
    "reply_count": int,
    v.Optional("action_counts"): v.Schema({
        "respect": int,
        "flag": int,
        "flag_comment_other": int,
        "flag_comment_offensive": int,
        "flag_spam_comment": int,
        "dontagree": int,
        "flag_trust": int,
        "flag_comment_spam": int,
        }, required=False),
    }, required=True)
s_old_comment_import = s_old_comment_base.extend({
    "metadata": v.Schema({
        "richTextBody": str,
        "source": "wpimport",
        }, required=True),
    }, required=True)
s_old_comment_organic = s_old_comment_base.extend({
    "body_history": [v.Schema({
        "_id": bson.objectid.ObjectId,
        "body": str,
        "created_at": datetime.datetime,
        }, required=True)],
    "tags": [v.Schema({
        "assigned_by": str,
        "tag": {
            "permissions": {
                "public": True, "roles": [v.Any("ADMIN", "MODERATOR")], "self": bool,
                },
            "models": ["COMMENTS"],
            "name": v.Any("STAFF", "OFF_TOPIC", "FEATURED"),
            "created_at": datetime.datetime,
            },
        "created_at": datetime.datetime,
        }, required=True)],
    "metadata": v.Schema({
        "richTextBody": str,
        v.Optional("akismet"): bool,
        }, required=True),
    "__v": int,
    }, required=True)
s_old_comment_deleted = v.Schema({
    "_id": bson.objectid.ObjectId,
    "id": str,
    "body": None,
    "body_history": [],
    "asset_id": str,
    "author_id": None,
    "status_history": [],
    "status": "ACCEPTED",
    "parent_id": v.Any(None, str),
    "reply_count": int,
    "action_counts": {},
    "tags": [],
    "metadata": {},
    "deleted_at": datetime.datetime,
    "created_at": datetime.datetime,
    "updated_at": datetime.datetime,
    }, required=True)
s_old_comment = v.Any(s_old_comment_organic, s_old_comment_import, s_old_comment_deleted)

s_old_action_ignore = v.Schema({
    "action_type": v.Any("FLAG", "DONTAGREE"),
    }, extra=v.ALLOW_EXTRA)
s_old_action_respect = v.Schema({
    "_id": bson.objectid.ObjectId,
    "action_type": "RESPECT",
    "group_id": None,
    "item_id": str,
    "item_type": "COMMENTS",
    "user_id": str,
    "__v": int,
    "created_at": datetime.datetime,
    "id": str,
    "metadata": {},
    "updated_at": datetime.datetime,
    }, required=True)
s_old_action = v.Any(s_old_action_ignore, s_old_action_respect)

c = pymongo.MongoClient()
olddb = c.talk
newdb = c.coral

tenantID = newdb.tenants.find_one()["id"]
site = newdb.sites.find_one()
siteID = site["id"]

site["commentCounts"]["action"]["REACTION"] = 0
for k in site["commentCounts"]["status"]:
    site["commentCounts"]["status"][k] = 0
site["commentCounts"]["moderationQueue"]["total"] = 0
for k in site["commentCounts"]["moderationQueue"]["queues"]:
    site["commentCounts"]["moderationQueue"]["queues"][k] = 0

print("translating stories...")
stories = []
stories_by_id = {}
stories_unicode = collections.defaultdict(list)
stories_unicode_replace = {}
stories_http = set()
def normalise(url):
    replacedhttp = False
    if url.startswith("http://"):
        url = "https://" + url[7:]
        replacedhttp = True
    if not url.startswith("https://www.angrymetalguy.com"):
        print(url)
        assert False
    host, path = url[:29], url[29:]
    if "%" in path:
        return host + urllib.parse.quote(urllib.parse.unquote(path)), True, replacedhttp
    for i in path:
        if ord(i) > 127:
            return host + urllib.parse.quote(path), True, replacedhttp
    if replacedhttp:
        return url, True, True
    return url, False, False
for story in olddb.assets.find():
    # things that need filling in later:
    # commentCounts, lastCommentedAt
    url, normed, httpnormed = normalise(story["url"])
    if normed or url in stories_http:
        stories_unicode[url].append(story["id"])
    if httpnormed:
        # ugh this is horrible
        stories_http.add(url)
        for story_exist in stories:
            if url == story_exist["url"]:
                stories_unicode[url].append(story_exist["id"])
        continue
    if story["scraped"] is None and story["metadata"].get("source", None) is None:
        #print("skipping probable unicode wonkiness", story["url"])
        continue
    if story.get("title", "").startswith("Page Not Found"):
        # spot of data cleaning while we're here
        continue
    try:
        s_old_story(story)
    except v.MultipleInvalid as e:
        pprint.pp(story)
        for i in e.errors:
            print(i)
        raise
    except v.Invalid:
        pprint.pp(story)
        raise
    if story.get("settings", {}) != {}:
        print("non-empty settings on", story["url"])
        pprint.pp(story["settings"])
    s = {
            "tenantID": tenantID,
            "siteID": siteID,
            "url": story["url"],
            "commentCounts": {
                "action": {
                    "REACTION": 0,
                    },
                "status": {
                    "APPROVED": 0,
                    "NONE": 0,
                    "PREMOD": 0,
                    "REJECTED": 0,
                    "SYSTEM_WITHHELD": 0,
                    },
                "moderationQueue": {
                    "total": 0,
                    "queues": {
                        "unmoderated": 0,
                        "reported": 0,
                        "pending": 0,
                        },
                    },
                },
            "settings": {},
            "createdAt": story["created_at"],
            "id": story["id"],
            "metadata": {
                "title": story["title"],
                "publishedAt": story["publication_date"],
                # author, description, image
                },
            "scrapedAt": story["scraped"],
            #"updatedAt": ,
            "lastCommentedAt": None,
            }
    if "source" in story["metadata"]:
        s["metadata"]["source"] = story["metadata"]["source"]
    for i in ["author", "description", "image"]:
        if i in story:
            s["metadata"][i] = story[i]
    stories.append(s)
    stories_by_id[s["id"]] = s

print("\nfixing unicode stories...")
rewritten = 0
redirected = 0
for url, ids in stories_unicode.items():
    if len(ids) == 1:
        s = stories_by_id[ids[0]]
        if s["url"] != url:
            print("rewrote", s["url"], "to", url)
            s["url"] = url
            rewritten += 1
    else:
        redirected += 1
        found_correct = None
        for id in ids:
            if id not in stories_by_id:
                # wonky record that was skipped
                continue
            s = stories_by_id[id]
            if s["url"] == url:
                found_correct = id
                print("mapping wonky urls to", url)
                break
        else:
            print("no correct url for", url)
            found_correct = s["id"]
            s["url"] = url
        for id in ids:
            if id == found_correct:
                continue
            stories_unicode_replace[id] = found_correct
            if id in stories_by_id:
                del stories_by_id[id]
stories = list(stories_by_id.values())
print("rewrote", rewritten, "to correct url normalisation")
print("redirected", redirected, "to correct url normalisation")

print("\ntranslating users...")
users = []
users_by_id = {}
deletedusers = set()
for user in olddb.users.find():
    # things that need filling in later:
    # commentCounts
    # things that might need filling in now but I have skipped:
    # the various history fields in status
    try:
        s_old_user(user)
    except v.MultipleInvalid as e:
        pprint.pp(user)
        for i in e.errors:
            print(i)
        raise
    except v.Invalid:
        pprint.pp(user)
        raise
    assert len(user["profiles"]) == 1
    if user.get("metadata", {}).get("avatar", "").startswith("data"):
        print("data url for", user["username"])
    u = {
            "tenantID": tenantID,
            "tokens": [],
            "ignoredUsers": [],
            "status": {
                "username": {"history": []},
                "suspension": {"history": []},
                "ban": {"active": False, "history": []},
                "premod": {"active": False, "history": []},
                "warning": {"active": False, "history": []},
                },
            "notifications": {
                "onReply": False,
                "onFeatured": False,
                "onModeration": False,
                "onStaffReplies": False,
                "digestFrequency": "NONE",
                },
            "moderatorNotes": [],
            "digests": [],
            "createdAt": user["created_at"],
            "commentCounts": {
                "status": {
                    "APPROVED": 0,
                    "NONE": 0,
                    "PREMOD": 0,
                    "REJECTED": 0,
                    "SYSTEM_WITHHELD": 0,
                    },
                },
            # email
            "username": user["username"],
            "role": user.get("role", "COMMENTER"),
            "profiles": [],
            "id": user["id"],
            # emailVerified
            "metadata": {},
            }
    if user.get("metadata", {}).get("source", "") == "wpimport":
        u["profiles"].append({"type": user["profiles"][0]["provider"], "id":user["profiles"][0]["id"]})
        u["metadata"]["source"] = "wpimport"
    else:
        if user["status"]["banned"]["status"]:
            u["status"]["ban"]["active"] = True
        if user["status"]["alwaysPremod"]["status"]:
            u["status"]["premod"]["active"] = True
        if user["ignoresUsers"]:
            u["ignoredUsers"] = user["ignoresUsers"]
        prof = user["profiles"][0]
        p = {}
        if prof["provider"] == "local":
            p["type"] = "local"
            p["id"] = prof["id"]
            p["password"] = user["password"]
            p["passwordID"] = str(uuid.uuid4())
            u["email"] = prof["id"]
            u["emailVerified"] = "confirmed_at" in prof.get("metadata", {})
        else:
            p["type"] = prof["provider"]
            p["id"] = prof["id"]
        u["profiles"].append(p)
        meta = user.get("metadata", {})
        if "avatar" in meta:
            av = meta["avatar"]
            if av != "" and not av.startswith("data:"):
                u["avatar"] = meta["avatar"]
        if "notifications" in meta:
            if meta["notifications"]["settings"].get("onReply", False):
                u["notifications"]["onReply"] = True
            if meta["notifications"]["settings"].get("onFeatured", False):
                u["notifications"]["onFeatured"] = True
            dig = meta["notifications"]["settings"].get("digestFrequency", "NONE")
            u["notifications"]["digestFrequency"] = dig
        if "scheduledDeletionDate" in meta:
            deletedusers.add(user["id"])
            continue
    users.append(u)
    users_by_id[u["id"]] = u

print("\ntranslating comments...")
comments = []
comments_by_id = {}
for comment in olddb.comments.find():
    # things that need filling in later:
    # childIDs, childCount, ancestorIDs
    try:
        s_old_comment(comment)
    except v.MultipleInvalid as e:
        pprint.pp(comment)
        for i in e.errors:
            print(i)
        raise
    except v.Invalid:
        pprint.pp(comment)
        raise
    if comment["asset_id"] in stories_unicode_replace:
        comment["asset_id"] = stories_unicode_replace[comment["asset_id"]]
    if comment["asset_id"] not in stories_by_id:
        # story skipped due to unicode issues, ignore comments
        continue
    c = {
            "id": comment["id"],
            "tenantID": tenantID,
            "childIDs": [],
            "childCount": 0,
            "revisions": [],
            "createdAt": comment["created_at"],
            "storyID": comment["asset_id"],
            "authorID": comment["author_id"],
            "siteID": siteID,
            "tags": [],
            "status": comment["status"] if comment["status"] != "ACCEPTED" else "APPROVED",
            "ancestorIDs": [],
            "actionCounts": {},
            "metadata": {},
            }
    parent = comment.get("parent_id")
    if parent:
        c["parentID"] = parent
    if "deleted_at" in comment:
        c["deletedAt"] = comment["deleted_at"]
    elif comment["author_id"] in deletedusers:
        c["authorID"] = None
        c["deletedAt"] = datetime.datetime.now()
    else:
        # not importing flags here
        act = {
                "REACTION": comment.get("action_counts", {}).get("respect", 0)
                }
        c["actionCounts"] = act
        # not reconstructing the full edit history here
        rev = {
                "id": str(uuid.uuid4()),
                "body": comment["metadata"]["richTextBody"],
                "actionCounts": act,
                "metadata": {"nudge": True, "linkCount": 0},
                "createdAt": comment["created_at"],
                }
        c["revisions"].append(rev)
        for tag in comment.get("tags", []):
            name = tag["tag"]["name"]
            ts = tag["created_at"]
            if name == "OFF_TOPIC":
                # no longer supported. put it somewhere we can get it back if we need to
                c["metadata"]["off_topic"] = True
            else:
                c["tags"].append({"type": name, "createdAt": ts})
        if comment.get("metadata", {}).get("source", "") == "wpimport":
            c["metadata"]["source"] = "wpimport"
        status = c["status"]
        story = stories_by_id[c["storyID"]]
        story["commentCounts"]["status"][status] += 1
        if story["lastCommentedAt"] == None or c["createdAt"] > story["lastCommentedAt"]:
            story["lastCommentedAt"] = c["createdAt"]
        user = users_by_id[c["authorID"]]
        user["commentCounts"]["status"][status] += 1
        site["commentCounts"]["status"][status] += 1
    comments.append(c)
    comments_by_id[c["id"]] = c

print("\nwalking comment tree...")
for c in comments:
    pid = c.get("parentID")
    if pid:
        p = comments_by_id.get(pid)
        if not p:
            del c["parentID"]
            continue
        if p["revisions"]:
            c["parentRevisionID"] = p["revisions"][0]["id"]
        else:
            c["parentRevisionID"] = None
        p["childIDs"].append(c["id"])
        p["childCount"] += 1
        while pid:
            c["ancestorIDs"].append(pid)
            pid = comments_by_id[pid].get("parentID")

print("\ntranslating actions...")
actions = []
for action in olddb.actions.find():
    try:
        s_old_action(action)
    except v.MultipleInvalid as e:
        pprint.pp(action)
        for i in e.errors:
            print(i)
        raise
    except v.Invalid:
        pprint.pp(action)
        raise
    if action["action_type"] != "RESPECT":
        continue
    comment = comments_by_id.get(action["item_id"])
    if not comment:
        # comment skipped due to story being skipped
        continue
    if not comment["revisions"]:
        # action on deleted comment
        continue
    a = {
            "actionType": "REACTION",
            "commentID": action["item_id"],
            "commentRevisionID": comment["revisions"][0]["id"],
            "siteID": siteID,
            "storyID": comment["storyID"],
            "tenantID": tenantID,
            "userID": action["user_id"],
            "additionalDetails": None,
            "createdAt": action["created_at"],
            "id": action["id"],
            }
    actions.append(a)
    story = stories_by_id[a["storyID"]]
    story["commentCounts"]["action"]["REACTION"] += 1
    site["commentCounts"]["action"]["REACTION"] += 1

print("\nready to insert into database")
input("ok?")

print("clearing old values")
newdb.commentActions.delete_many({})
newdb.commentModerationActions.delete_many({})
newdb.comments.delete_many({})
newdb.users.delete_many({})
newdb.stories.delete_many({})

print("writing users")
newdb.users.insert_many(users)
print("writing stories")
newdb.stories.insert_many(stories)
print("writing comments")
newdb.comments.insert_many(comments)
print("writing actions")
newdb.commentActions.insert_many(actions)
print("fixing site comment count")
newdb.sites.replace_one({"id": siteID}, site)
