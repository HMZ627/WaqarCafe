import html
from pathlib import Path
import streamlit as st

from utils.styles import GLOBAL_CSS
from utils.security import (
    check_rate_limit,
    generate_order_id,
    sanitize_text,
    validate_and_clean_receipt,
    validate_phone,
)
from utils.webhooks import (
    send_bug_webhook,
    send_order_webhook,
    send_review_webhook,
)

# -----------------------------------------------------------------------------
# Page Config & Initialization (Zero Emojis)
# -----------------------------------------------------------------------------
logo_page_icon = "static/Logo.png" if Path("static/Logo.png").exists() else None

st.set_page_config(
    page_title="Waqar Foodies | Flavour After Darkness",
    page_icon=logo_page_icon,
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.html(GLOBAL_CSS)

MENU_ITEMS = {
    "tower_burger": {
        "id": "tower_burger",
        "name": "Tower Burger",
        "price": 500,
        "image": "static/tower_burger.png",
        "desc": "Charcoal-seared double beef patty, melted aged cheddar, crisp greens, pickles, and signature burger sauce on toasted sesame brioche.",
    },
    "paratha_roll": {
        "id": "paratha_roll",
        "name": "Chicken Paratha Roll",
        "price": 350,
        "image": "static/paratha_roll.png",
        "desc": "Flaky golden-crisped paratha wrapped around smoky chargrilled chicken tikka, pickled red onions, and signature mint-garlic crema.",
    },
}

if "page" not in st.session_state:
    st.session_state.page = "Home"
if "cart" not in st.session_state:
    st.session_state.cart = {}
if "saved_customer" not in st.session_state:
    st.session_state.saved_customer = None
if "open_checkout_modal" not in st.session_state:
    st.session_state.open_checkout_modal = False
if "confirmed_order_id" not in st.session_state:
    st.session_state.confirmed_order_id = None


# -----------------------------------------------------------------------------
# Cart Helpers
# -----------------------------------------------------------------------------
def add_to_cart(item_id: str, qty: int = 1):
    st.session_state.cart[item_id] = st.session_state.cart.get(item_id, 0) + qty


def update_cart_qty(item_id: str, delta: int):
    new_qty = st.session_state.cart.get(item_id, 0) + delta
    if new_qty <= 0:
        st.session_state.cart.pop(item_id, None)
    else:
        st.session_state.cart[item_id] = new_qty


def get_cart_summary() -> tuple[list[dict], int, int]:
    items = []
    total_qty = 0
    grand_total = 0
    for item_id, qty in st.session_state.cart.items():
        if item_id in MENU_ITEMS and qty > 0:
            meta = MENU_ITEMS[item_id]
            items.append({"id": item_id, "name": meta["name"], "price": meta["price"], "qty": qty})
            total_qty += qty
            grand_total += meta["price"] * qty
    return items, total_qty, grand_total


# -----------------------------------------------------------------------------
# Modals (Order Checkout & Order Confirmation)
# -----------------------------------------------------------------------------
@st.dialog("Complete Your Order", width="large")
def show_checkout_dialog():
    cart_items, _, grand_total = get_cart_summary()
    if not cart_items:
        st.warning("Your order bag is empty. Please add an item from the Menu first.")
        if st.button("Go to Menu", type="primary"):
            st.session_state.page = "Menu"
            st.rerun()
        return

    top_alert = st.empty()

    st.markdown("#### Order Summary")
    for item in cart_items:
        st.write(f"• **{item['name']}** x {item['qty']} — `PKR {item['price'] * item['qty']:,}/-`")
    st.markdown(f"**Grand Total:** :orange[**PKR {grand_total:,}/-**]")
    st.divider()

    saved = st.session_state.saved_customer or {}

    name_input = st.text_input(
        "Full Name *",
        value=saved.get("name", ""),
        max_chars=80,
        placeholder="e.g. Waqar Ahmed",
    )
    address_input = st.text_area(
        "Delivery Address *",
        value=saved.get("address", ""),
        max_chars=250,
        height=80,
        placeholder="House #, Street, Sector / Area, City",
    )
    phone_input = st.text_input(
        "Phone Number *",
        value=saved.get("phone", ""),
        max_chars=20,
        placeholder="03XXXXXXXXX",
    )

    payment_method = st.radio(
        "Payment Method *",
        options=["Cash on Delivery (COD)", "Online (JazzCash)"],
        horizontal=True,
    )

    uploaded_receipt = None
    if payment_method == "Online (JazzCash)":
        jc_number = html.escape(str(st.secrets.get("JAZZCASH_NUMBER", "0300-0000000")))
        jc_title = html.escape(str(st.secrets.get("JAZZCASH_NAME", "Waqar Foodies")))
        st.html(
            f"""
            <div class="wf-jazzcash-box">
                <div style="font-weight:700; color:#F0CA5A; margin-bottom:4px;">JazzCash Transfer Details</div>
                <div>Account Number: <strong style="font-size:1.1rem; letter-spacing:1px;">{jc_number}</strong></div>
                <div>Account Title: <strong>{jc_title}</strong></div>
                <div style="font-size:0.86rem; color:#CFC4B4; margin-top:6px;">
                    Please transfer <strong>PKR {grand_total:,}/-</strong> and upload your payment screenshot below (Max 2 MB).
                </div>
            </div>
            """
        )
        uploaded_receipt = st.file_uploader(
            "Upload Payment Screenshot * (PNG/JPG/WEBP, Max 2 MB)",
            type=["png", "jpg", "jpeg", "webp"],
            accept_multiple_files=False,
        )

    save_details = st.checkbox(
        "Save order details for future orders",
        value=False,
        help="Keeps your name, address, and phone only inside your private browser session.",
    )

    bottom_alert = st.empty()

    if st.button("Confirm Order", type="primary", use_container_width=True):
        clean_name = sanitize_text(name_input, max_len=80)
        clean_addr = sanitize_text(address_input, max_len=250)
        valid_phone, clean_phone = validate_phone(phone_input)

        missing_errors = []
        if len(clean_name) < 2:
            missing_errors.append("Full Name is required.")
        if len(clean_addr) < 8:
            missing_errors.append("Complete Delivery Address is required.")
        if not valid_phone:
            missing_errors.append("Valid Phone Number is required (e.g. 03001234567).")

        receipt_bytes = None
        receipt_name = None
        if payment_method == "Online (JazzCash)":
            ok_img, receipt_bytes, receipt_name, img_err = validate_and_clean_receipt(uploaded_receipt)
            if not ok_img:
                missing_errors.append(img_err)

        if missing_errors:
            warning_msg = "**Please complete all required order details:**\n\n" + "\n".join(
                f"- {err}" for err in missing_errors
            )
            top_alert.error(warning_msg)
            bottom_alert.error(warning_msg)
            st.toast("Please fill in all crucial order details.")
            return

        allowed, wait_sec = check_rate_limit("order_submit", cooldown_seconds=20)
        if not allowed:
            bottom_alert.warning(f"Please wait {wait_sec}s before placing another order.")
            return

        order_id = generate_order_id()

        with st.spinner("Sending your order securely..."):
            sent = send_order_webhook(
                order_id=order_id,
                name=clean_name,
                address=clean_addr,
                phone=clean_phone,
                payment_method=payment_method,
                items=cart_items,
                grand_total=grand_total,
                receipt_bytes=receipt_bytes,
                receipt_filename=receipt_name,
            )

        if not sent:
            bottom_alert.error("Unable to submit order right now. Please try again shortly.")
            return

        if save_details:
            st.session_state.saved_customer = {
                "name": clean_name,
                "address": clean_addr,
                "phone": clean_phone,
            }
        else:
            st.session_state.saved_customer = None

        st.session_state.cart = {}
        st.session_state.confirmed_order_id = order_id
        st.rerun()


@st.dialog("Order Confirmed")
def show_confirmation_dialog(order_id: str):
    st.html(
        f"""
        <div style="text-align:center;">
            <div style="color:#CFC4B4; margin-top:4px; font-size:0.95rem; letter-spacing:1px; text-transform:uppercase;">
                Your Order ID
            </div>
            <div class="wf-order-id-box">
                <div class="wf-order-id-code" id="wf-order-id-text">{order_id}</div>
            </div>
            <button id="wf-copy-btn"
                style="background:linear-gradient(135deg,#D4AF37,#B88E24); color:#121212;
                       border:none; border-radius:999px; padding:8px 22px; font-weight:700;
                       cursor:pointer; margin-bottom:12px;">
                Copy Order ID
            </button>
            <div id="wf-copy-status" style="font-size:0.85rem; color:#D4AF37; min-height:20px;"></div>
            <p style="color:#F5EFE6; font-size:1.02rem; margin-top:10px; font-weight:500;">
                You will be confirmed for your order shortly, <strong>THANK YOU!</strong>
            </p>
        </div>
        <script>
        const btn = document.getElementById('wf-copy-btn');
        if (btn) {{
            btn.addEventListener('click', async () => {{
                try {{
                    await navigator.clipboard.writeText("{order_id}");
                    document.getElementById('wf-copy-status').textContent = "Copied to clipboard!";
                }} catch (e) {{
                    document.getElementById('wf-copy-status').textContent = "Select and copy the ID above.";
                }}
            }});
        }}
        </script>
        """,
        unsafe_allow_javascript=True,
    )
    st.code(order_id, language=None)
    if st.button("Done", type="primary", use_container_width=True):
        st.session_state.confirmed_order_id = None
        st.rerun()


if st.session_state.confirmed_order_id:
    show_confirmation_dialog(st.session_state.confirmed_order_id)
elif st.session_state.open_checkout_modal:
    st.session_state.open_checkout_modal = False
    show_checkout_dialog()


# -----------------------------------------------------------------------------
# Top Toolbar (Larger Logo Left + Menu / Review / Report a bug + Bag Icon)
# -----------------------------------------------------------------------------
def render_navbar():
    cart_items, total_qty, grand_total = get_cart_summary()

    col_brand, col_menu, col_review, col_bug, col_bag = st.columns(
        [3.1, 0.9, 0.9, 1.25, 0.65], vertical_alignment="center"
    )

    with col_brand:
        logo_exists = Path("static/Logo.png").exists()
        logo_html = (
            '<img src="./app/static/Logo.png" class="wf-brand-logo" alt="Waqar Foodies Logo" />'
            if logo_exists
            else ""
        )
        c_logo, c_home = st.columns([3.4, 1.0], vertical_alignment="center")
        with c_logo:
            st.html(
                f"""
                <div class="wf-brand-wrap">
                    {logo_html}
                    <span class="wf-brand-name">Waqar Foodies</span>
                </div>
                """
            )
        with c_home:
            if st.button("Home", key="nav_home"):
                st.session_state.page = "Home"
                st.rerun()

    with col_menu:
        if st.button(
            "Menu",
            key="nav_menu",
            type="primary" if st.session_state.page == "Menu" else "secondary",
            use_container_width=True,
        ):
            st.session_state.page = "Menu"
            st.rerun()

    with col_review:
        if st.button(
            "Review",
            key="nav_review",
            type="primary" if st.session_state.page == "Review" else "secondary",
            use_container_width=True,
        ):
            st.session_state.page = "Review"
            st.rerun()

    with col_bug:
        if st.button(
            "Report a bug",
            key="nav_bug",
            type="primary" if st.session_state.page == "Bug" else "secondary",
            use_container_width=True,
        ):
            st.session_state.page = "Bug"
            st.rerun()

    with col_bag:
        with st.popover(str(total_qty), key="bag_popover", help="Your Order Bag"):
            st.markdown("#### Your Order")
            if not cart_items:
                st.caption("No items added yet.")
            else:
                for item in cart_items:
                    r1, r2, r3, r4 = st.columns([2.3, 0.85, 0.85, 1.2], vertical_alignment="center")
                    with r1:
                        st.markdown(f"**{item['name']}**")
                        st.caption(f"PKR {item['price']:,} x {item['qty']}")
                    with r2:
                        if st.button("-", key=f"dec_{item['id']}"):
                            update_cart_qty(item["id"], -1)
                            st.rerun()
                    with r3:
                        if st.button("+", key=f"inc_{item['id']}"):
                            update_cart_qty(item["id"], +1)
                            st.rerun()
                    with r4:
                        st.markdown(f"**{item['price'] * item['qty']:,}**")

                st.divider()
                st.markdown(f"**Grand Total:** :orange[**PKR {grand_total:,}/-**]")
                if st.button("Order", key="basket_order_btn", type="primary", use_container_width=True):
                    st.session_state.open_checkout_modal = True
                    st.rerun()

    st.html('<div class="wf-nav-divider"></div>')


# -----------------------------------------------------------------------------
# Review & Bug Report Sections
# -----------------------------------------------------------------------------
def render_review_section(standalone: bool = False):
    st.html(
        """
        <div class="wf-blur-in" style="margin-top: 2.5rem;">
            <h2 class="wf-section-title">Leave a <span>Review</span></h2>
            <p class="wf-section-sub">Loved the crunch, smoke, and warmth? Tell us how your experience tasted.</p>
        </div>
        """
    )
    _, center_col, _ = st.columns([1, 2.2, 1])
    with center_col:
        with st.container(border=True):
            reviewer_name = st.text_input(
                "Your Name (Optional)",
                max_chars=60,
                placeholder="e.g. Ali",
                key=f"rev_name_{standalone}",
            )
            st.markdown("**Rate Your Experience:**")
            rating_idx = st.feedback("stars", key=f"rev_stars_{standalone}")
            review_text = st.text_area(
                "Your Review",
                max_chars=800,
                height=130,
                placeholder="Write your thoughts about the Tower Burger, Chicken Paratha Roll, or cafe vibe...",
                key=f"rev_text_{standalone}",
            )
            if st.button("Submit", key=f"rev_submit_{standalone}", type="primary", use_container_width=True):
                if rating_idx is None:
                    st.error("Please select a star rating (1 to 5 stars).")
                    return
                clean_rev = sanitize_text(review_text, max_len=800)
                clean_name = sanitize_text(reviewer_name, max_len=60) or "Guest"
                if len(clean_rev) < 5:
                    st.error("Please write at least a few words in your review.")
                    return

                allowed, wait_sec = check_rate_limit("review_submit", cooldown_seconds=15)
                if not allowed:
                    st.warning(f"Please wait {wait_sec}s before submitting another review.")
                    return

                stars = rating_idx + 1
                with st.spinner("Submitting review..."):
                    ok = send_review_webhook(stars=stars, review_text=clean_rev, reviewer_name=clean_name)
                if ok:
                    st.success("Thank you. Your review has been sent to Waqar Foodies.")
                else:
                    st.error("Could not send review right now. Please try again shortly.")


def render_bug_page():
    st.html(
        """
        <div class="wf-blur-in" style="margin-top: 1.5rem;">
            <h2 class="wf-section-title">Report a <span>Bug</span></h2>
            <p class="wf-section-sub">Spotted an issue on our website? Let us know and we will fix it right away.</p>
        </div>
        """
    )
    _, center_col, _ = st.columns([1, 2.2, 1])
    with center_col:
        with st.container(border=True):
            reporter_name = st.text_input(
                "Your Name (Optional)",
                max_chars=60,
                placeholder="Anonymous",
                key="bug_name",
            )
            bug_text = st.text_area(
                "Describe the Bug",
                max_chars=1000,
                height=160,
                placeholder="What happened, which page were you on, and what device/browser are you using?",
                key="bug_text",
            )
            if st.button("Submit", key="bug_submit", type="primary", use_container_width=True):
                clean_bug = sanitize_text(bug_text, max_len=1000)
                clean_name = sanitize_text(reporter_name, max_len=60) or "Anonymous"
                if len(clean_bug) < 8:
                    st.error("Please provide a clear description of the bug.")
                    return

                allowed, wait_sec = check_rate_limit("bug_submit", cooldown_seconds=15)
                if not allowed:
                    st.warning(f"Please wait {wait_sec}s before submitting another report.")
                    return

                with st.spinner("Sending bug report..."):
                    ok = send_bug_webhook(bug_text=clean_bug, reporter_name=clean_name)
                if ok:
                    st.success("Bug report received. Thank you for helping improve Waqar Foodies.")
                else:
                    st.error("Could not send bug report right now. Please try again later.")


# -----------------------------------------------------------------------------
# Menu Page
# -----------------------------------------------------------------------------
def render_menu_page():
    st.html(
        """
        <div class="wf-blur-in">
            <h2 class="wf-section-title">Our <span>Signature</span> Menu</h2>
            <p class="wf-section-sub">Handcrafted fresh after sundown. Choose your cravings below.</p>
        </div>
        """
    )

    col1, col2 = st.columns(2, gap="large")
    for col, item_key in zip([col1, col2], ["tower_burger", "paratha_roll"]):
        item = MENU_ITEMS[item_key]
        with col:
            with st.container():
                img_path = Path(item["image"])
                img_html = (
                    f'<img src="./app/{item["image"]}" style="width:100%; height:230px; object-fit:cover; border-radius:14px;" alt="{item["name"]}"/>'
                    if img_path.exists()
                    else f'<div class="wf-menu-placeholder">{item["name"]}</div>'
                )
                st.html(
                    f"""
                    <div class="wf-menu-card wf-blur-in">
                        {img_html}
                        <div class="wf-menu-title">{item['name']}</div>
                        <div class="wf-menu-price">{item['price']}/- PKR</div>
                        <div class="wf-menu-desc">{item['desc']}</div>
                    </div>
                    """
                )
                b1, b2 = st.columns(2)
                with b1:
                    if st.button("Order now", key=f"order_now_{item_key}", type="primary", use_container_width=True):
                        if st.session_state.cart.get(item_key, 0) == 0:
                            add_to_cart(item_key, 1)
                        st.session_state.open_checkout_modal = True
                        st.rerun()
                with b2:
                    if st.button("Add to Order", key=f"add_order_{item_key}", use_container_width=True):
                        add_to_cart(item_key, 1)
                        st.toast(f"Added {item['name']} to your order.")
                        st.rerun()


# -----------------------------------------------------------------------------
# Home Page
# -----------------------------------------------------------------------------
def render_home_page():
    # 1. Intro Fade-In / Fade-Out Overlay -> Triggers Main Page Fade-In-Blur-In
    st.html(
        """
        <style>
        #wf-intro-overlay {
            position: fixed;
            inset: 0;
            z-index: 999999;
            background: #121212;
            display: flex;
            align-items: center;
            justify-content: center;
            opacity: 1;
            transition: opacity 1s ease;
        }
        #wf-intro-overlay.wf-removed {
            display: none !important;
            pointer-events: none !important;
        }
        #wf-intro-video {
            width: 100%;
            height: 100%;
            object-fit: cover;
            opacity: 0;
            transition: opacity 1.1s ease;
        }
        #wf-intro-skip {
            position: absolute;
            bottom: 32px;
            right: 32px;
            background: rgba(18, 18, 18, 0.72);
            color: #F5EFE6;
            border: 1px solid rgba(212, 175, 55, 0.45);
            border-radius: 999px;
            padding: 8px 20px;
            font-weight: 600;
            font-size: 0.85rem;
            cursor: pointer;
            z-index: 2;
        }
        #wf-intro-skip:hover {
            border-color: #D4AF37;
            color: #D4AF37;
        }
        </style>

        <div id="wf-intro-overlay">
            <video id="wf-intro-video" autoplay muted playsinline preload="auto">
                <source src="./app/static/intro.mp4" type="video/mp4" />
            </video>
            <button id="wf-intro-skip" type="button">Skip</button>
        </div>

        <script>
        (function() {
            const overlay = document.getElementById('wf-intro-overlay');
            const vid = document.getElementById('wf-intro-video');
            const skipBtn = document.getElementById('wf-intro-skip');
            const appRoot = document.querySelector('[data-testid="stAppViewContainer"]');

            if (window.__wfIntroDone) {
                if (overlay) overlay.classList.add('wf-removed');
                return;
            }

            let finished = false;

            function finishIntro() {
                if (finished) return;
                finished = true;
                window.__wfIntroDone = true;
                overlay.style.opacity = '0';

                if (appRoot) {
                    appRoot.classList.remove('wf-blur-in');
                    void appRoot.offsetWidth;
                    appRoot.classList.add('wf-blur-in');
                }

                setTimeout(() => {
                    overlay.classList.add('wf-removed');
                }, 1050);
            }

            function startPlayback() {
                vid.muted = true;
                vid.style.opacity = '1';
                const playPromise = vid.play();
                if (playPromise && typeof playPromise.catch === 'function') {
                    playPromise.catch(() => {
                        setTimeout(() => {
                            if (vid.paused && !finished) finishIntro();
                        }, 1200);
                    });
                }
            }

            vid.addEventListener('loadeddata', startPlayback);
            vid.addEventListener('canplay', startPlayback);

            vid.addEventListener('timeupdate', () => {
                if (vid.duration && vid.duration - vid.currentTime <= 0.85) {
                    finishIntro();
                }
            });

            vid.addEventListener('ended', finishIntro);
            vid.addEventListener('error', finishIntro);

            const sourceEl = vid.querySelector('source');
            if (sourceEl) {
                sourceEl.addEventListener('error', finishIntro);
            }

            skipBtn.addEventListener('click', finishIntro);

            vid.load();
            setTimeout(() => {
                if (!finished && vid.readyState === 0) {
                    finishIntro();
                } else if (!finished && vid.paused) {
                    startPlayback();
                }
            }, 4500);
        })();
        </script>
        """,
        unsafe_allow_javascript=True,
    )

    # 2. Hero Header
    st.html(
        """
        <style>
        .wf-hero {
            text-align: center;
            padding: 2.2rem 1rem 3.2rem 1rem;
            min-height: 52vh;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
        }
        .wf-hero-kicker {
            display: inline-block;
            color: #D4AF37;
            border: 1px solid rgba(212, 175, 55, 0.35);
            background: rgba(212, 175, 55, 0.08);
            border-radius: 999px;
            padding: 0.32rem 1.15rem;
            font-size: 0.8rem;
            letter-spacing: 2.2px;
            text-transform: uppercase;
            margin-bottom: 1.3rem;
        }
        .wf-hero-heading {
            font-family: 'Playfair Display', serif;
            color: #F5EFE6;
            line-height: 1.18;
            margin: 0 auto;
            max-width: 960px;
        }
        .wf-w-flavour {
            font-family: 'Lobster', cursive;
            font-size: clamp(3.4rem, 7vw, 5.8rem);
            color: #D4AF37;
            text-shadow: 0 4px 26px rgba(212, 175, 55, 0.35);
        }
        .wf-w-small {
            font-size: clamp(1.35rem, 2.6vw, 2.1rem);
            font-weight: 400;
            color: #E6DAC8;
            font-style: italic;
        }
        .wf-w-alive {
            font-size: clamp(2.2rem, 4.2vw, 3.4rem);
            font-weight: 800;
            color: #F5EFE6;
            letter-spacing: 1px;
        }
        .wf-w-darkness {
            font-size: clamp(3.2rem, 6.5vw, 5.4rem);
            font-weight: 900;
            background: linear-gradient(180deg, #FFF5DC 0%, #D4AF37 55%, #8C6A15 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            filter: drop-shadow(0 6px 24px rgba(212, 175, 55, 0.25));
        }
        .wf-hero-scroll-cue {
            margin-top: 2.2rem;
            font-size: 0.78rem;
            letter-spacing: 2.4px;
            text-transform: uppercase;
            color: rgba(245, 239, 230, 0.45);
        }
        </style>
        <div class="wf-hero wf-blur-in">
            <div class="wf-hero-kicker">Late-Night Artisan Cafe</div>
            <h1 class="wf-hero-heading">
                <span class="wf-w-flavour">Flavour</span><span class="wf-w-small">, that comes</span>
                <span class="wf-w-alive"> Alive </span>
                <span class="wf-w-small">After </span>
                <span class="wf-w-darkness">Darkness</span>
            </h1>
            <div class="wf-hero-scroll-cue">Scroll Down to Experience</div>
        </div>
        """
    )

    # 3. Full-Screen Seamless Scroll-Controlled Showcase
    st.html(
        """
        <style>
        #wf-fullscreen-stage {
            position: relative;
            width: 100vw;
            left: 50%;
            transform: translateX(-50%);
            height: 100vh;
            min-height: 620px;
            overflow: hidden;
            display: flex;
            align-items: center;
            justify-content: center;
            background: radial-gradient(circle at 50% 48%, #4A3514 0%, #14120D 68%, #0E0D0B 100%);
            transition: background 1.1s cubic-bezier(0.22, 1, 0.36, 1);
        }

        .wf-stage-visual-wrap {
            position: absolute;
            inset: 0;
            display: flex;
            align-items: center;
            justify-content: center;
            pointer-events: none;
            z-index: 1;
        }

        #wf-burger-canvas-video {
            height: 100vh;
            width: auto;
            max-width: 100vw;
            object-fit: contain;
            -webkit-mask-image: radial-gradient(ellipse 52% 68% at 50% 50%, #000 54%, rgba(0,0,0,0.45) 78%, transparent 100%);
            mask-image: radial-gradient(ellipse 52% 68% at 50% 50%, #000 54%, rgba(0,0,0,0.45) 78%, transparent 100%);
            opacity: 0.96;
        }

        .wf-side-grid {
            position: relative;
            z-index: 4;
            width: 100%;
            max-width: 1380px;
            padding: 0 3.5vw;
            display: grid;
            grid-template-columns: 1fr 1.15fr 1fr;
            align-items: center;
            gap: 2rem;
            pointer-events: none;
        }

        .wf-side-left {
            text-align: left;
            padding: 1.2rem 1.4rem;
            border-left: 2px solid rgba(212, 175, 55, 0.65);
            background: linear-gradient(90deg, rgba(14, 13, 11, 0.65), transparent);
            border-radius: 0 14px 14px 0;
        }

        .wf-side-right {
            text-align: right;
            padding: 1.2rem 1.4rem;
            border-right: 2px solid rgba(212, 175, 55, 0.65);
            background: linear-gradient(-90deg, rgba(14, 13, 11, 0.65), transparent);
            border-radius: 14px 0 0 14px;
        }

        .wf-side-spacer {
            min-height: 10px;
        }

        .wf-source-label {
            font-size: 0.76rem;
            letter-spacing: 2.2px;
            text-transform: uppercase;
            color: #D4AF37;
            margin-bottom: 0.55rem;
            font-weight: 600;
        }

        .wf-side-subheader {
            font-family: 'Playfair Display', serif;
            font-size: clamp(1.75rem, 2.8vw, 2.7rem);
            color: #F5EFE6;
            line-height: 1.18;
            margin: 0;
            text-shadow: 0 4px 20px rgba(0, 0, 0, 0.85);
        }

        .wf-side-body {
            color: #EAE0D2;
            font-size: clamp(0.95rem, 1.25vw, 1.12rem);
            line-height: 1.7;
            margin: 0;
            text-shadow: 0 2px 14px rgba(0, 0, 0, 0.9);
        }

        @keyframes wfTextBlurIn {
            0% {
                opacity: 0;
                filter: blur(16px);
                transform: translateY(14px);
            }
            100% {
                opacity: 1;
                filter: blur(0px);
                transform: translateY(0);
            }
        }

        .wf-side-animate {
            animation: wfTextBlurIn 0.9s cubic-bezier(0.22, 1, 0.36, 1) forwards;
        }

        .wf-side-hidden {
            opacity: 0;
            filter: blur(14px);
        }

        .wf-stage-progress {
            position: absolute;
            right: 22px;
            top: 50%;
            transform: translateY(-50%);
            z-index: 6;
            display: flex;
            flex-direction: column;
            gap: 10px;
        }

        .wf-prog-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: rgba(245, 239, 230, 0.25);
            border: 1px solid rgba(212, 175, 55, 0.45);
            cursor: pointer;
            transition: all 0.3s ease;
        }

        .wf-prog-dot.active {
            height: 26px;
            border-radius: 999px;
            background: #D4AF37;
        }

        @media (max-width: 900px) {
            .wf-side-grid {
                grid-template-columns: 1fr;
                height: 88vh;
                align-content: space-between;
                padding: 1.5rem 1.2rem;
            }
            .wf-side-spacer {
                display: none;
            }
            .wf-side-left, .wf-side-right {
                text-align: center;
                border: none;
                background: rgba(14, 13, 11, 0.62);
                border-radius: 14px;
            }
        }
        </style>

        <div id="wf-fullscreen-stage">
            <div class="wf-stage-visual-wrap">
                <video id="wf-burger-canvas-video" muted playsinline preload="auto">
                    <source src="./app/static/burger_prep.mp4" type="video/mp4" />
                </video>
            </div>

            <div class="wf-side-grid">
                <div class="wf-side-left wf-side-animate" id="wf-left-text">
                    <div class="wf-source-label" id="wf-ing-source">Sunlit Golden Wheat Fields</div>
                    <h2 class="wf-side-subheader" id="wf-ing-sub">Toasted Sesame Brioche Bun</h2>
                </div>

                <div class="wf-side-spacer"></div>

                <div class="wf-side-right wf-side-animate" id="wf-right-text">
                    <p class="wf-side-body" id="wf-ing-body">
                        Harvested from golden wheat fields and baked pillowy-soft with toasted sesame seeds, splitting open in warm millstone mist.
                    </p>
                </div>
            </div>

            <div class="wf-stage-progress" id="wf-stage-dots"></div>
        </div>

        <script>
        (function() {
            const stage = document.getElementById('wf-fullscreen-stage');
            const video = document.getElementById('wf-burger-canvas-video');
            const leftBox = document.getElementById('wf-left-text');
            const rightBox = document.getElementById('wf-right-text');
            const sourceEl = document.getElementById('wf-ing-source');
            const subEl = document.getElementById('wf-ing-sub');
            const bodyEl = document.getElementById('wf-ing-body');
            const dotsWrap = document.getElementById('wf-stage-dots');

            if (!stage || !video) return;

            const sections = [
                {
                    pct: 0.00,
                    source: "Sunlit Golden Wheat Fields",
                    sub: "Toasted Sesame Brioche Bun",
                    body: "Harvested from golden wheat fields and baked pillowy-soft with toasted sesame seeds, splitting open in warm millstone mist.",
                    bg: "radial-gradient(circle at 50% 48%, #4F3814 0%, #17130D 65%, #0D0C0A 100%)"
                },
                {
                    pct: 0.23,
                    source: "Morning Dew Vegetable Farms",
                    sub: "Crisp Lettuce, Vine Tomatoes & Red Onions",
                    body: "Dew-fresh emerald lettuce, sun-ripened tomato slices, and sharp purple onion rings cascading straight from fertile garden soil.",
                    bg: "radial-gradient(circle at 50% 48%, #153D23 0%, #0E1711 65%, #0B0E0C 100%)"
                },
                {
                    pct: 0.43,
                    source: "Lush Green Dairy Pastures",
                    sub: "Creamy Double Cheddar & Crisp Pickles",
                    body: "Wholesome pasture milk churned into two rich, velvety cheddar slices, layered generously over tangy dill pickles and greens.",
                    bg: "radial-gradient(circle at 50% 48%, #2E3F19 0%, #15170F 65%, #0C0D0A 100%)"
                },
                {
                    pct: 0.64,
                    source: "Twilight Wood-Fired Grill",
                    sub: "Double Charcoal-Seared Beef Patties",
                    body: "Two thick, hand-pressed beef patties seared at dusk over roaring hardwood flames—locking in smoky char and sizzling juices.",
                    bg: "radial-gradient(circle at 50% 48%, #521A0E 0%, #180E0D 65%, #0D0A0A 100%)"
                },
                {
                    pct: 0.98,
                    source: "Waqar Foodies — After Darkness",
                    sub: "The Signature Double Tower Burger",
                    body: "Crowned with crushed peppercorns, signature house burger sauce, and warm golden bokeh—crafted to come alive after darkness.",
                    bg: "radial-gradient(circle at 50% 48%, #36240B 0%, #12100D 65%, #0A0A09 100%)"
                }
            ];

            let currentStep = 0;
            let isBusy = false;
            let animFrame = null;

            dotsWrap.innerHTML = "";
            sections.forEach((_, idx) => {
                const dot = document.createElement('div');
                dot.className = 'wf-prog-dot' + (idx === 0 ? ' active' : '');
                dot.addEventListener('click', () => {
                    if (!isBusy) goToStep(idx);
                });
                dotsWrap.appendChild(dot);
            });

            function applySideText(stepIdx) {
                const s = sections[stepIdx];
                stage.style.background = s.bg;

                Array.from(dotsWrap.children).forEach((d, i) => {
                    d.classList.toggle('active', i === stepIdx);
                });

                leftBox.classList.remove('wf-side-animate');
                rightBox.classList.remove('wf-side-animate');
                leftBox.classList.add('wf-side-hidden');
                rightBox.classList.add('wf-side-hidden');

                setTimeout(() => {
                    sourceEl.textContent = s.source;
                    subEl.textContent = s.sub;
                    bodyEl.textContent = s.body;
                    leftBox.classList.remove('wf-side-hidden');
                    rightBox.classList.remove('wf-side-hidden');
                    void leftBox.offsetWidth;
                    leftBox.classList.add('wf-side-animate');
                    rightBox.classList.add('wf-side-animate');
                }, 140);
            }

            function easeInOutCubic(t) {
                return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
            }

            function playSegmentSlowly(targetPct) {
                if (animFrame) cancelAnimationFrame(animFrame);
                const duration = video.duration;
                if (!duration || isNaN(duration)) {
                    isBusy = false;
                    return;
                }

                const startTime = video.currentTime;
                const endTime = Math.min(duration - 0.05, Math.max(0, targetPct * duration));
                const distance = endTime - startTime;

                if (Math.abs(distance) < 0.04) {
                    video.pause();
                    isBusy = false;
                    return;
                }

                const animDurationMs = Math.max(1650, Math.min(2400, Math.abs(distance) * 950));
                const startClock = performance.now();
                const goingForward = distance > 0;

                if (goingForward) {
                    video.muted = true;
                    video.playbackRate = 0.35;
                    video.play().catch(() => {});
                } else {
                    video.pause();
                }

                function frame(now) {
                    const elapsed = now - startClock;
                    const progress = Math.min(1, elapsed / animDurationMs);
                    const eased = easeInOutCubic(progress);

                    if (goingForward && !video.paused) {
                        const speedBell = Math.sin(progress * Math.PI);
                        const avgRate = distance / (animDurationMs / 1000);
                        video.playbackRate = Math.min(1.6, Math.max(0.22, avgRate * (0.35 + 1.05 * speedBell)));

                        if (progress >= 1 || video.currentTime >= endTime) {
                            video.pause();
                            video.currentTime = endTime;
                            isBusy = false;
                            return;
                        }
                    } else {
                        video.currentTime = startTime + distance * eased;
                        if (progress >= 1) {
                            video.pause();
                            video.currentTime = endTime;
                            isBusy = false;
                            return;
                        }
                    }

                    animFrame = requestAnimationFrame(frame);
                }

                animFrame = requestAnimationFrame(frame);
            }

            function goToStep(nextIdx) {
                if (nextIdx < 0 || nextIdx >= sections.length || nextIdx === currentStep) return;
                isBusy = true;
                currentStep = nextIdx;
                applySideText(currentStep);
                playSegmentSlowly(sections[currentStep].pct);
                setTimeout(() => { isBusy = false; }, 1900);
            }

            function snapToStage() {
                isBusy = true;
                const rect = stage.getBoundingClientRect();
                window.scrollTo({
                    top: window.scrollY + rect.top,
                    behavior: 'smooth'
                });
                setTimeout(() => { isBusy = false; }, 850);
            }

            if (window.__wfStageWheelHandler) {
                window.removeEventListener('wheel', window.__wfStageWheelHandler);
            }

            window.__wfStageWheelHandler = function(e) {
                if (!document.body.contains(stage)) {
                    window.removeEventListener('wheel', window.__wfStageWheelHandler);
                    return;
                }
                if (Math.abs(e.deltaY) < 6) return;

                const rect = stage.getBoundingClientRect();

                if (rect.top > 45 && rect.top < window.innerHeight * 1.15 && e.deltaY > 0) {
                    e.preventDefault();
                    if (!isBusy) snapToStage();
                    return;
                }

                if (Math.abs(rect.top) <= 45) {
                    if (e.deltaY > 0) {
                        if (currentStep < sections.length - 1) {
                            e.preventDefault();
                            if (!isBusy) goToStep(currentStep + 1);
                        }
                    } else {
                        if (currentStep > 0) {
                            e.preventDefault();
                            if (!isBusy) goToStep(currentStep - 1);
                        }
                    }
                    return;
                }

                if (rect.top < -45 && rect.bottom > window.innerHeight * 0.45 && e.deltaY < 0) {
                    e.preventDefault();
                    if (!isBusy) snapToStage();
                }
            };

            window.addEventListener('wheel', window.__wfStageWheelHandler, { passive: false });

            let tY = null;
            stage.addEventListener('touchstart', (e) => { tY = e.touches[0].clientY; }, { passive: true });
            stage.addEventListener('touchend', (e) => {
                if (tY === null) return;
                const diff = tY - e.changedTouches[0].clientY;
                tY = null;
                if (Math.abs(diff) < 35 || isBusy) return;
                if (diff > 0 && currentStep < sections.length - 1) goToStep(currentStep + 1);
                else if (diff < 0 && currentStep > 0) goToStep(currentStep - 1);
            }, { passive: true });

            video.addEventListener('loadedmetadata', () => {
                video.currentTime = 0;
                video.pause();
            });
        })();
        </script>
        """,
        unsafe_allow_javascript=True,
    )

    _, cta_col, _ = st.columns([1.4, 1.2, 1.4])
    with cta_col:
        st.write("")
        st.write("")
        if st.button("Order Now", key="home_order_now", type="primary", use_container_width=True):
            st.session_state.page = "Menu"
            st.rerun()

    # 4. Bounded Auto-Scrolling & User-Scrollable Blurred Testimonials Carousel
    st.html(
        """
        <div class="wf-blur-in" style="margin-top:3.2rem;">
            <h2 class="wf-section-title">Voices After <span>Darkness</span></h2>
            <p class="wf-section-sub">Scroll or select any review to explore what our regulars say.</p>
        </div>

        <style>
        #wf-testi-box {
            position: relative;
            height: 410px;
            max-width: 740px;
            margin: 0 auto;
            overflow: hidden;
            border-radius: 24px;
            background: radial-gradient(circle at 50% 50%, rgba(212, 175, 55, 0.08), #141311 78%);
            border: 1px solid rgba(212, 175, 55, 0.22);
            perspective: 900px;
            user-select: none;
            cursor: ns-resize;
        }
        #wf-testi-box::before,
        #wf-testi-box::after {
            content: "";
            position: absolute;
            left: 0;
            right: 0;
            height: 75px;
            z-index: 10;
            pointer-events: none;
        }
        #wf-testi-box::before {
            top: 0;
            background: linear-gradient(180deg, #121212 10%, transparent 100%);
        }
        #wf-testi-box::after {
            bottom: 0;
            background: linear-gradient(0deg, #121212 10%, transparent 100%);
        }
        .wf-t-card {
            position: absolute;
            left: 50%;
            top: 50%;
            width: 86%;
            max-width: 580px;
            padding: 1.35rem 1.7rem;
            border-radius: 18px;
            background: linear-gradient(145deg, #1E1C17, #161512);
            border: 1px solid rgba(212, 175, 55, 0.2);
            transition: all 0.72s cubic-bezier(0.22, 1, 0.36, 1);
            box-sizing: border-box;
        }
        .wf-t-card[data-pos="0"] {
            transform: translate(-50%, -50%) scale(1) rotateX(0deg);
            filter: blur(0px);
            opacity: 1;
            z-index: 5;
            border-color: #D4AF37;
            box-shadow: 0 18px 42px rgba(0, 0, 0, 0.65), 0 0 24px rgba(212, 175, 55, 0.18);
        }
        .wf-t-card[data-pos="-1"] {
            transform: translate(-50%, -138%) scale(0.86) rotateX(18deg) skewX(-1.5deg);
            filter: blur(4px) contrast(0.9);
            opacity: 0.45;
            z-index: 3;
        }
        .wf-t-card[data-pos="1"] {
            transform: translate(-50%, 38%) scale(0.86) rotateX(-18deg) skewX(1.5deg);
            filter: blur(4px) contrast(0.9);
            opacity: 0.45;
            z-index: 3;
        }
        .wf-t-card[data-pos="-2"] {
            transform: translate(-50%, -215%) scale(0.74) rotateX(28deg) skewX(-3deg);
            filter: blur(8px);
            opacity: 0.14;
            z-index: 1;
        }
        .wf-t-card[data-pos="2"] {
            transform: translate(-50%, 115%) scale(0.74) rotateX(-28deg) skewX(3deg);
            filter: blur(8px);
            opacity: 0.14;
            z-index: 1;
        }
        .wf-t-quote {
            color: #F5EFE6;
            font-size: 1rem;
            line-height: 1.55;
            font-style: italic;
            margin-bottom: 0.7rem;
        }
        .wf-t-author {
            display: flex;
            align-items: center;
            justify-content: space-between;
            color: #D4AF37;
            font-weight: 700;
            font-size: 0.96rem;
        }
        .wf-svg-stars {
            display: inline-flex;
            gap: 3px;
            align-items: center;
        }
        </style>

        <div id="wf-testi-box"></div>

        <script>
        (function() {
            const box = document.getElementById('wf-testi-box');
            const reviews = [
                { name: "Ali", text: "The Tower Burger after midnight is unbeatable. That smoky charcoal sear and warm buttered brioche hit different every single time." },
                { name: "Abdullah", text: "Ordered the Chicken Paratha Roll with friends — flaky, juicy, and packed with spice. Easily the best late-night cafe vibe around." },
                { name: "Umer", text: "Dark charcoal aesthetic, super smooth service, and the signature sauce on the burger is pure perfection. My regular weekend stop." },
                { name: "Ahmed", text: "Fast order confirmation and piping hot delivery. Waqar Foodies never compromises on ingredient freshness." },
                { name: "Junaid", text: "From the first bite to the last crumb, you can taste the craft. Top marks for both the Tower Burger and Paratha Roll." }
            ];

            const starSvg = `<svg width="14" height="14" viewBox="0 0 24 24" fill="#D4AF37"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>`;
            const fiveStars = `<span class="wf-svg-stars">${starSvg.repeat(5)}</span>`;

            let activeIdx = 0;
            let autoTimer = null;
            let resumeTimeout = null;
            let wheelLock = false;

            const cards = reviews.map((rev, idx) => {
                const el = document.createElement('div');
                el.className = 'wf-t-card';
                el.innerHTML = `
                    <div class="wf-t-quote">“${rev.text}”</div>
                    <div class="wf-t-author">
                        <span>— ${rev.name}</span>
                        ${fiveStars}
                    </div>
                `;
                el.addEventListener('click', () => {
                    activeIdx = idx;
                    layout();
                    resetAuto(6000);
                });
                box.appendChild(el);
                return el;
            });

            function layout() {
                const n = reviews.length;
                cards.forEach((card, i) => {
                    let diff = i - activeIdx;
                    if (diff > Math.floor(n / 2)) diff -= n;
                    if (diff < -Math.floor(n / 2)) diff += n;
                    card.setAttribute('data-pos', String(diff));
                });
            }

            function step(dir) {
                activeIdx = (activeIdx + dir + reviews.length) % reviews.length;
                layout();
            }

            function resetAuto(pauseMs = 3400) {
                if (autoTimer) clearInterval(autoTimer);
                if (resumeTimeout) clearTimeout(resumeTimeout);
                resumeTimeout = setTimeout(() => {
                    autoTimer = setInterval(() => step(1), 3400);
                }, pauseMs === 3400 ? 0 : pauseMs);
            }

            box.addEventListener('wheel', (e) => {
                e.preventDefault();
                if (wheelLock || Math.abs(e.deltaY) < 6) return;
                wheelLock = true;
                step(e.deltaY > 0 ? 1 : -1);
                resetAuto(5500);
                setTimeout(() => { wheelLock = false; }, 320);
            }, { passive: false });

            let tStartY = null;
            box.addEventListener('touchstart', (e) => { tStartY = e.touches[0].clientY; }, { passive: true });
            box.addEventListener('touchend', (e) => {
                if (tStartY === null) return;
                const d = tStartY - e.changedTouches[0].clientY;
                tStartY = null;
                if (Math.abs(d) > 25) {
                    step(d > 0 ? 1 : -1);
                    resetAuto(5500);
                }
            }, { passive: true });

            layout();
            autoTimer = setInterval(() => step(1), 3400);
        })();
        </script>
        """,
        unsafe_allow_javascript=True,
    )

    # 5. Review Section
    render_review_section(standalone=False)


# -----------------------------------------------------------------------------
# Router
# -----------------------------------------------------------------------------
render_navbar()

if st.session_state.page == "Home":
    render_home_page()
elif st.session_state.page == "Menu":
    render_menu_page()
elif st.session_state.page == "Review":
    render_review_section(standalone=True)
elif st.session_state.page == "Bug":
    render_bug_page()
