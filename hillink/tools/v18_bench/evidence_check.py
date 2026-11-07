"""No-cost check: are this customer's records about the shown restaurants actually sent?

For every shown meal candidate, the records of the FULL persona block that name the restaurant by its
hotel-specific name (the existing alias list; generic service names such as room service are excluded,
because another hotel's room service is not this venue) and are not explicitly about another hotel
(source_scope 'other'). Each such record is an experience the guest had with an option on the table —
positive, negative or mixed (polarity is not annotated; the model reads the summary). The check lists
the ones a variant did not send. It reads records only; it decides nothing about preference.

Used by the bench driver (offline and live) to record, per variant, `venue_records_unsent`.
"""
GENERIC_VENUES = {'ROOM_MEAL'}   # a service every hotel has; its name does not identify this hotel's venue


def venue_named_records(personal, rows, venue_names):
    out = {}
    cite = set(personal.get('citable_fact_ids') or [])
    records = personal.get('evidence_records') or personal.get('records') or []
    for r in rows:
        if r.get('type') != 'MEAL': continue
        venue = r['action_id'].split(':', 1)[1]
        if venue in GENERIC_VENUES: continue
        names = venue_names(venue)
        for rec in records:
            if rec.get('source_scope') == 'other': continue
            text = str(rec.get('summary') or '')
            ids = [f for f in rec.get('fact_ids') or [] if f in cite]
            if ids and any(n and n in text for n in names):
                out.setdefault(r['action_id'], []).append(dict(fact_ids=ids, source_scope=rec.get('source_scope')))
    return out


def unsent(full_personal, rows, sent_ids, venue_names):
    sent = set(sent_ids or [])
    miss = {}
    for action, recs in venue_named_records(full_personal, rows, venue_names).items():
        lost = [dict(rec, fact_ids=rec['fact_ids']) for rec in recs if not set(rec['fact_ids']) & sent]
        if lost: miss[action] = lost
    return miss
