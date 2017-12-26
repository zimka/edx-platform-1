from collections import namedtuple
from dateutil import parser
import datetime
import json


SessionEntry = namedtuple("SessionEntry", ['key', 'ip'])


class ExamSessionSet:
    """
    Contains info about user sessions: when it was observed, session key and IP-address.
    """
    def __init__(self, sessions_dict={}):
        self._sessions = sessions_dict

    @property
    def sessions(self):
        return set(self._sessions.values())

    def add(self, session_entry):
        """
        Adds session_entry if it wasn't seen earlier.
        Doesn't change date-key for session_entry if it was seen.
        """
        if session_entry in self:
            return
        date = datetime.datetime.now()
        self._sessions[date] = session_entry

    def to_json(self):
        to_str = lambda x: x.isoformat()
        session_dict = dict((json.dumps(k, default=to_str), json.dumps(v._asdict())) for k,v in self._sessions.iteritems())
        return json.dumps(session_dict)

    def is_suspicious(self):
        return len(self._sessions) > 1

    def pretty_repr(self):
        """
        Returns list of strings for each seen session
        """
        date_keys = sorted(self._sessions.keys())
        data = self._sessions
        template = "At {date}: {ip}('{session_key}')"
        strings = [
            template.format(date=k, ip=data[k].ip, session_key=data[k].key)
            for k in date_keys
        ]
        return strings

    @classmethod
    def from_json(cls, serial):
        session_dict_str = json.loads(serial)
        from_str = lambda x: parser.parse(x)
        session_dict = dict((
            from_str(json.loads(k)),
            SessionEntry(**json.loads(v))
            )
            for k,v in session_dict_str.iteritems())
        return cls(session_dict)

    def __contains__(self, item):
        return item in self.sessions

    def __repr__(self):
        return "SessionExamSet<" + ",".join(["['{}':{}]".format(k,v) for k, v in self._sessions.iteritems()]) + ">"

    def __add__(self, other):
        """
        Adding works like set, dates are not considered
        """
        if other is None:
            return self
        combined_dict = dict(self._sessions)
        for key in other._sessions:
            if other._sessions[key] not in combined_dict.values():
                combined_dict[key] = other._sessions[key]
        return ExamSessionSet(combined_dict)

    def __eq__(self, other):
        if not isinstance(other, ExamSessionSet):
            return False
        return self.sessions == other.sessions


def _get_client_ip(request):
    """
    Extracts user ip from request
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[-1].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def get_session_entry(request):
    """
    Builds session entry for given request
    """
    ip = _get_client_ip(request)
    session_key = request.session.session_key
    return SessionEntry(ip=ip, key=session_key)
