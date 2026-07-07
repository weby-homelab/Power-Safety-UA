from app.parser_service import _is_private_host


class TestSSRFBlocklist:
    """Test SSRF protection for custom URLs."""

    def test_localhost_blocked(self):
        assert _is_private_host("localhost") is True
        assert _is_private_host("127.0.0.1") is True

    def test_private_ranges_blocked(self):
        assert _is_private_host("10.0.0.1") is True
        assert _is_private_host("192.168.1.1") is True
        assert _is_private_host("172.16.0.1") is True
        assert _is_private_host("169.254.169.254") is True

    def test_ipv6_private_blocked(self):
        assert _is_private_host("::1") is True

    def test_public_domain_allowed(self):
        assert _is_private_host("example.com") is False
        assert _is_private_host("google.com") is False

    def test_public_ip_allowed(self):
        assert _is_private_host("8.8.8.8") is False

    def test_zero_ip_private(self):
        assert _is_private_host("0.0.0.0") is True

    def test_link_local_ipv6_blocked(self):
        assert _is_private_host("fe80::1") is True

    def test_unique_local_ipv6_blocked(self):
        assert _is_private_host("fc00::1") is True

    def test_invalid_hostname_blocked(self):
        assert _is_private_host("invalid-hostname-that-wont-resolve.invalid") is True
