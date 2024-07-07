"""Implementation of the incompatibility check for SameSite=None setting of cookies. The check is based on Chromium's
pseudo code: https://www.chromium.org/updates/same-site/incompatible-clients """

import re


def should_set_same_site_to_none(user_agent: str) -> bool:
    return user_agent and not is_same_site_none_incompatible(user_agent)


def is_same_site_none_incompatible(user_agent: str) -> bool:
    return has_web_kit_same_site_bug(
        user_agent
    ) or drops_unrecognized_same_site_cookies(user_agent)


def has_web_kit_same_site_bug(user_agent: str) -> bool:
    return is_ios_version(major=12, user_agent=user_agent) or (
        is_osx_version(major=10, minor=14, user_agent=user_agent)
        and (is_safari(user_agent) or is_mac_embedded_browser(user_agent))
    )


def drops_unrecognized_same_site_cookies(user_agent: str) -> bool:
    if is_uc_browser(user_agent):
        return not is_uc_browser_version_at_least(
            major=12, minor=13, build=2, user_agent=user_agent
        )
    return (
        is_chromium_based(user_agent)
        and is_chromium_version_at_least(major=51, user_agent=user_agent)
        and not is_chromium_version_at_least(major=67, user_agent=user_agent)
    )


def is_ios_version(major: int, user_agent: str) -> bool:
    pattern = r"\(iP.+; CPU .*OS (\d+)[_\d]*.*\) AppleWebKit\/"
    # Extract digits from first capturing group.
    match = re.search(pattern, user_agent)
    return match and int(match.group(1)) == major


def is_osx_version(major: int, minor: int, user_agent: str) -> bool:
    pattern = r"\(Macintosh;.*Mac OS X (\d+)_(\d+)[_\d]*.*\) AppleWebKit\/"
    # Extract digits from first and second capturing groups.
    match = re.search(pattern, user_agent)
    return match and int(match.group(1)) == major and int(match.group(2)) == minor


def is_safari(user_agent: str) -> bool:
    pattern = r"Version\/.* Safari\/"
    return re.search(pattern, user_agent) and not is_chromium_based(user_agent)


def is_mac_embedded_browser(user_agent: str) -> bool:
    pattern = r"^Mozilla\/[\.\d]+ \(Macintosh;.*Mac OS X [_\d]+\) AppleWebKit\/[\.\d]+ \(KHTML, like Gecko\)$"
    return re.search(pattern, user_agent) is not None


def is_chromium_based(user_agent: str) -> bool:
    return "Chrome" in user_agent or "Chromium" in user_agent


def is_chromium_version_at_least(major: int, user_agent: str) -> bool:
    pattern = r"Chrom[^ \/]+\/(\d+)[\.\d]* "
    # First capturing group is the version
    match = re.search(pattern, user_agent)
    return match and int(match.group(1)) >= major


def is_uc_browser(user_agent: str) -> bool:
    return "UCBrowser/" in user_agent


def is_uc_browser_version_at_least(major: int, minor: int, build: int, user_agent: str) -> bool:
    pattern = r"UCBrowser\/(\d+)\.(\d+)\.(\d+)[\.\d]* "
    # Extract digits from three capturing groups.
    match = re.search(pattern, user_agent)
    if not match:
        return False
    major_version = int(match.group(1))
    minor_version = int(match.group(2))
    build_version = int(match.group(3))
    if major_version != major:
        return major_version > major
    if minor_version != minor:
        return minor_version > minor
    return build_version >= build
