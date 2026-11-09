"""
CampusConnect Security Engine.
Provides Bot Protection (Honeypot + Dynamic Arithmetic CAPTCHA),
Brute-Force Rate Limiting, and Comprehensive Security Auditing.
"""

import time
import random
import hashlib
from django.conf import settings
from django.core.cache import cache
from reports.utils import get_client_ip, log_audit


class SecurityCaptcha:
    """
    Dynamic arithmetic & logic CAPTCHA challenge generator & validator.
    Works entirely offline without third-party external service dependencies.
    """

    @staticmethod
    def generate_challenge(request):
        """Generates a dynamic arithmetic puzzle and saves the answer in session."""
        operations = ['+', '-', '*']
        op = random.choice(operations)

        if op == '+':
            n1 = random.randint(4, 25)
            n2 = random.randint(2, 18)
            question = f"{n1} + {n2}"
            answer = n1 + n2
        elif op == '-':
            n1 = random.randint(10, 35)
            n2 = random.randint(2, n1 - 1)
            question = f"{n1} - {n2}"
            answer = n1 - n2
        else:  # multiplication
            n1 = random.randint(2, 9)
            n2 = random.randint(2, 8)
            question = f"{n1} × {n2}"
            answer = n1 * n2

        token = hashlib.sha256(
            f"{question}:{answer}:{time.time()}:{settings.SECRET_KEY}".encode('utf-8')
        ).hexdigest()[:16]

        request.session['captcha_token'] = token
        request.session['captcha_answer'] = str(answer)
        request.session['captcha_created_at'] = time.time()

        return {
            'question': question,
            'token': token,
            'answer': str(answer),  # Provided for 1-click demo autofill convenience
        }

    @staticmethod
    def verify(request, user_answer):
        """
        Validates the user's submitted CAPTCHA answer.
        Invalidates challenge after validation to prevent replay attacks.
        """
        stored_answer = request.session.get('captcha_answer')
        created_at = request.session.get('captcha_created_at', 0)

        # Invalidate current session challenge immediately to prevent replays
        request.session.pop('captcha_answer', None)
        request.session.pop('captcha_token', None)
        request.session.pop('captcha_created_at', None)

        if not stored_answer:
            return False, "Security verification session expired. Please solve the new challenge."

        expiry = getattr(settings, 'CAPTCHA_EXPIRY_SECONDS', 600)
        if time.time() - created_at > expiry:
            return False, "Security verification expired. Please solve the fresh puzzle."

        if not user_answer or not str(user_answer).strip():
            return False, "Security verification answer is required."

        if str(user_answer).strip() != str(stored_answer).strip():
            return False, "Incorrect security verification answer. Please try again."

        return True, None


class BotHoneypot:
    """
    Invisible honeypot protection against automated scrapers and bots.
    Bots auto-fill all form inputs, while human browsers leave hidden traps blank.
    """
    FIELD_NAME = 'portal_auth_trap'

    @classmethod
    def is_bot_detected(cls, request):
        trap_value = request.POST.get(cls.FIELD_NAME, '')
        return bool(trap_value and trap_value.strip())


class LoginRateLimiter:
    """
    Protects user accounts and system against automated brute-force attacks
    and credential stuffing by tracking consecutive failed attempts.
    """

    @staticmethod
    def _ip_key(ip):
        return f"cc_rl_ip_{ip}"

    @staticmethod
    def _user_key(username):
        clean_user = (username or '').strip().lower()
        return f"cc_rl_user_{clean_user}"

    @classmethod
    def is_rate_limited(cls, request, username):
        """Checks if the client IP or attempted username has exceeded failed login thresholds."""
        max_attempts = getattr(settings, 'LOGIN_MAX_FAILED_ATTEMPTS', 5)
        ip = get_client_ip(request) or '127.0.0.1'

        ip_failures = cache.get(cls._ip_key(ip), 0)
        user_failures = cache.get(cls._user_key(username), 0) if username else 0

        if ip_failures >= max_attempts or user_failures >= max_attempts:
            cooldown_min = getattr(settings, 'LOGIN_LOCKOUT_SECONDS', 900) // 60
            return True, f"Too many failed login attempts. For institutional security, access is temporarily locked. Please wait {cooldown_min} minutes."
        return False, None

    @classmethod
    def record_failure(cls, request, username):
        """Increments failed attempt counters and triggers security audit events."""
        ip = get_client_ip(request) or '127.0.0.1'
        lockout = getattr(settings, 'LOGIN_LOCKOUT_SECONDS', 900)
        max_attempts = getattr(settings, 'LOGIN_MAX_FAILED_ATTEMPTS', 5)

        ip_key = cls._ip_key(ip)
        user_key = cls._user_key(username)

        ip_count = cache.get(ip_key, 0) + 1
        user_count = cache.get(user_key, 0) + 1

        cache.set(ip_key, ip_count, lockout)
        if username:
            cache.set(user_key, user_count, lockout)

        highest = max(ip_count, user_count)
        if highest >= max_attempts:
            log_audit(
                request=request,
                action="BRUTE_FORCE_LOCKOUT",
                entity_type="SecurityFirewall",
                entity_id=ip,
                details=f"Brute-force limit ({max_attempts} attempts) reached for user '{username}' from IP {ip}. Cooldown lockout initiated."
            )
        else:
            log_audit(
                request=request,
                action="LOGIN_FAILED",
                entity_type="CustomUser",
                entity_id=username or "Unknown",
                details=f"Invalid login credentials for '{username}' from IP {ip} (Attempt {highest}/{max_attempts})."
            )

    @classmethod
    def reset(cls, request, username):
        """Resets failed attempt counters upon successful authentication."""
        ip = get_client_ip(request) or '127.0.0.1'
        cache.delete(cls._ip_key(ip))
        if username:
            cache.delete(cls._user_key(username))
