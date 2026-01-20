"""Authentication utilities for magic link auth with Supabase."""

import streamlit as st
from urllib.parse import urlparse, parse_qs
from utils.supabase_client import get_supabase_client


def init_auth_state():
    """Initialize authentication session state variables."""
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if "user_email" not in st.session_state:
        st.session_state.user_email = None
    if "magic_link_sent" not in st.session_state:
        st.session_state.magic_link_sent = False
    if "pending_email" not in st.session_state:
        st.session_state.pending_email = None
    if "access_token" not in st.session_state:
        st.session_state.access_token = None
    if "refresh_token" not in st.session_state:
        st.session_state.refresh_token = None


def send_magic_link(email: str) -> tuple[bool, str]:
    """Send a magic link to the user's email.

    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        client = get_supabase_client()
        response = client.auth.sign_in_with_otp({
            "email": email,
            "options": {
                "should_create_user": False
            }
        })
        st.session_state.magic_link_sent = True
        st.session_state.pending_email = email
        return True, "Magic link sent! Check your email and paste the token from the URL below."
    except Exception as e:
        error_msg = str(e)
        if "User not found" in error_msg or "user not found" in error_msg.lower():
            return False, "Email not authorized for admin access."
        return False, f"Failed to send magic link: {error_msg}"


def parse_token_from_input(input_str: str) -> tuple[str | None, str | None]:
    """Parse access_token and refresh_token from URL or direct token input.

    The magic link redirects to a URL like:
    http://localhost:3000/#access_token=...&refresh_token=...&...

    Returns:
        tuple: (access_token, refresh_token) or (None, None) if parsing fails
    """
    input_str = input_str.strip()

    # Check if it's a URL with hash fragment
    if "#" in input_str:
        # Extract the fragment part after #
        fragment = input_str.split("#", 1)[1]
        # Parse the fragment as query string
        params = parse_qs(fragment)
        access_token = params.get("access_token", [None])[0]
        refresh_token = params.get("refresh_token", [None])[0]
        return access_token, refresh_token

    # Check if input contains access_token= (fragment without URL)
    if "access_token=" in input_str:
        params = parse_qs(input_str)
        access_token = params.get("access_token", [None])[0]
        refresh_token = params.get("refresh_token", [None])[0]
        return access_token, refresh_token

    # Assume it's a direct access token
    return input_str, None


def verify_with_token(access_token: str, refresh_token: str | None = None) -> tuple[bool, str]:
    """Verify authentication using access token from magic link.

    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        from utils.supabase_client import _create_client
        client = _create_client()

        # Set the session using the tokens from the magic link
        response = client.auth.set_session(access_token, refresh_token or "")

        if response.user:
            # Store tokens in session state for authenticated client to use
            st.session_state.access_token = access_token
            st.session_state.refresh_token = refresh_token
            st.session_state.authenticated = True
            st.session_state.user_email = response.user.email
            st.session_state.magic_link_sent = False
            st.session_state.pending_email = None
            return True, "Successfully authenticated!"
        return False, "Invalid or expired token."
    except Exception as e:
        return False, f"Verification failed: {str(e)}"


def logout():
    """Log out the current user."""
    try:
        client = get_supabase_client()
        client.auth.sign_out()
    except Exception:
        pass

    st.session_state.authenticated = False
    st.session_state.user_email = None
    st.session_state.magic_link_sent = False
    st.session_state.pending_email = None
    st.session_state.access_token = None
    st.session_state.refresh_token = None


def is_authenticated() -> bool:
    """Check if the user is authenticated."""
    init_auth_state()
    return st.session_state.authenticated


def get_current_user_email() -> str | None:
    """Get the email of the currently authenticated user."""
    return st.session_state.get("user_email")


def render_login_form():
    """Render the login form UI.

    Returns:
        bool: True if user is authenticated after form submission
    """
    init_auth_state()

    if st.session_state.authenticated:
        return True

    st.subheader("Admin Login")

    if not st.session_state.magic_link_sent:
        with st.form("magic_link_form"):
            email = st.text_input("Email", placeholder="Enter your admin email")
            submitted = st.form_submit_button("Send Magic Link", use_container_width=True)

            if submitted:
                if not email:
                    st.error("Please enter your email.")
                elif "@" not in email:
                    st.error("Please enter a valid email address.")
                else:
                    with st.spinner("Sending magic link..."):
                        success, message = send_magic_link(email)
                    if success:
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)
    else:
        st.info(f"Magic link sent to **{st.session_state.pending_email}**")
        st.caption(
            "Click the link in your email. You'll be redirected to a localhost page. "
            "Copy the **full URL** from your browser's address bar and paste it below."
        )

        with st.form("verify_token_form"):
            token_input = st.text_input(
                "Paste URL or Token",
                placeholder="http://localhost:3000/#access_token=... or just the token"
            )
            col1, col2 = st.columns(2)

            with col1:
                verify_submitted = st.form_submit_button("Verify", use_container_width=True)
            with col2:
                cancel_submitted = st.form_submit_button("Cancel", use_container_width=True)

            if verify_submitted:
                if not token_input:
                    st.error("Please paste the URL or token from the magic link.")
                else:
                    access_token, refresh_token = parse_token_from_input(token_input)
                    if not access_token:
                        st.error("Could not parse token from input. Please paste the full URL.")
                    else:
                        with st.spinner("Verifying..."):
                            success, message = verify_with_token(access_token, refresh_token)
                        if success:
                            st.success(message)
                            st.rerun()
                        else:
                            st.error(message)

            if cancel_submitted:
                st.session_state.magic_link_sent = False
                st.session_state.pending_email = None
                st.rerun()

    return False


def render_logout_button():
    """Render a logout button in the sidebar."""
    if st.session_state.get("authenticated"):
        with st.sidebar:
            st.divider()
            st.caption(f"Logged in as: {st.session_state.user_email}")
            if st.button("Logout", use_container_width=True):
                logout()
                st.rerun()
