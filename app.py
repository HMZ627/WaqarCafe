import html
from pathlib import Path
from urllib.parse import urlparse
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
# Page Config & Initialization
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


@st.cache_resource
def get_live_reviews_store() -> list[dict]:
    """Shared in-memory review store seeded with core testimonials; fresh user reviews appear live."""
    return [
        {
            "name": "Ali",
            "stars": 5,
            "text": "The Tower Burger after midnight is unbeatable. That smoky charcoal sear and warm buttered brioche hit different every single time.",
        },
        {
            "name": "Abdullah",
            "stars": 5,
            "text": "Ordered the Chicken Paratha Roll with friends — flaky, juicy, and packed with spice. Easily the best late-night cafe vibe around.",
        },
        {
            "name": "Umer",
            "stars": 5,
            "text": "Dark charcoal aesthetic, super smooth service, and the signature sauce on the burger is pure perfection. My regular weekend stop.",
        },
        {
            "name": "Ahmed",
            "stars": 5,
            "text": "Fast order confirmation and piping hot delivery. Waqar Foodies never compromises on ingredient freshness.",
        },
        {
            "name": "Junaid",
            "stars": 5,
            "text": "From the first bite to the last crumb, you can taste the craft. Top marks for both the Tower Burger and Paratha Roll.",
        },
    ]


if "cart" not in st.session_state:
    st.session_state.cart = {}
if "saved_customer" not in st.session_state:
    st.session_state.saved_customer = None
if "open_checkout_modal" not in st.session_state:
    st.session_state.open_checkout_modal = False
if "confirmed_order_id" not in st.session_state:
    st.session_state.confirmed_order_id = None
if "review_submitted_notice" not in st.session_state:
    st.session_state.review_submitted_notice = False


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
    st.html(
        """
        <script>
        (function() {
            const popBodies = document.querySelectorAll('[data-testid="stPopoverBody"]:not([data-wf-ghost])');
            if (popBodies.length > 0) {
                document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
                const bagBtn = document.querySelector('.st-key-bag_popover button');
                if (bagBtn && bagBtn.getAttribute('aria-expanded') === 'true') {
                    bagBtn.click();
                }
            }
        })();
        </script>
        """,
        unsafe_allow_javascript=True,
    )

    cart_items, _, grand_total = get_cart_summary()
    if not cart_items:
        st.warning("Your order bag is empty. Please add an item from the Menu first.")
        if st.button("Go to Menu", type="primary"):
            st.switch_page(menu_page)
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
        jazzcash_html = """
            <div class="wf-jazzcash-box">
                <div style="font-weight:700; color:#F0CA5A; margin-bottom:4px;">JazzCash Transfer Details</div>
                <div>Account Number: <strong style="font-size:1.1rem; letter-spacing:1px;">__JC_NUMBER__</strong></div>
                <div>Account Title: <strong>__JC_TITLE__</strong></div>
                <div style="font-size:0.86rem; color:#CFC4B4; margin-top:6px;">
                    Please transfer <strong>PKR __TOTAL__/-</strong> and upload your payment screenshot below (Max 2 MB).
                </div>
            </div>
        """.replace("__JC_NUMBER__", jc_number).replace("__JC_TITLE__", jc_title).replace("__TOTAL__", f"{grand_total:,}")
        st.html(jazzcash_html)
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
    confirm_html = """
        <div style="text-align:center;">
            <div style="color:#CFC4B4; margin-top:4px; font-size:0.95rem; letter-spacing:1px; text-transform:uppercase;">
                Your Order ID
            </div>
            <div class="wf-order-id-box">
                <div class="wf-order-id-code" id="wf-order-id-text">__ORDER_ID__</div>
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
        (function() {
            const btn = document.getElementById('wf-copy-btn');
            if (btn) {
                btn.addEventListener('click', async () => {
                    try {
                        await navigator.clipboard.writeText("__ORDER_ID__");
                        document.getElementById('wf-copy-status').textContent = "Copied to clipboard!";
                    } catch (e) {
                        document.getElementById('wf-copy-status').textContent = "Select and copy the ID above.";
                    }
                });
            }
        })();
        </script>
    """.replace("__ORDER_ID__", html.escape(order_id))

    st.html(confirm_html, unsafe_allow_javascript=True)
    st.code(order_id, language=None)
    if st.button("Done", type="primary", use_container_width=True):
        st.session_state.confirmed_order_id = None
        st.rerun()


def detach_home_listeners_js():
    """Ensure Home spatial scroll listeners and hidden-page states are cleared on subpages."""
    st.html(
        """
        <script>
        (function() {
            if (window.__wfDetachSpatial) window.__wfDetachSpatial();
            const nav = document.querySelector('.st-key-navbar_wrap');
            if (nav) {
                nav.classList.remove('wf-page-hidden');
            }
        })();
        </script>
        """,
        unsafe_allow_javascript=True,
    )


# -----------------------------------------------------------------------------
# Custom 404 Page (/404)
# -----------------------------------------------------------------------------
def render_404_page():
    detach_home_listeners_js()
    missing_path = html.escape(str(st.session_state.get("_missing_path", "")))
    path_badge = (
        f'<div class="wf-404-path">Requested Path: <span>{missing_path}</span></div>'
        if missing_path
        else ""
    )

    page_404_html = """
        <style>
        .wf-404-wrap {
            max-width: 720px;
            margin: 1.5rem auto 2rem auto;
            padding: 3rem 2rem;
            text-align: center;
            border-radius: 26px;
            background: radial-gradient(circle at 50% 25%, rgba(212, 175, 55, 0.14), #151412 76%);
            border: 1px solid rgba(212, 175, 55, 0.34);
            box-shadow: 0 24px 64px rgba(0, 0, 0, 0.65);
        }
        .wf-404-code {
            font-family: 'Playfair Display', serif;
            font-size: clamp(5rem, 12vw, 8.5rem);
            font-weight: 900;
            line-height: 0.95;
            background: linear-gradient(180deg, #FFF5DC 0%, #D4AF37 55%, #8C6A15 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            filter: drop-shadow(0 8px 26px rgba(212, 175, 55, 0.28));
            margin-bottom: 0.5rem;
        }
        .wf-404-title {
            font-family: 'Great Vibes', cursive;
            font-size: clamp(2.4rem, 5vw, 3.6rem);
            color: #F5EFE6;
            margin: 0.2rem 0 0.8rem 0;
            font-weight: 400;
        }
        .wf-404-msg {
            color: #CFC4B4;
            font-size: 1rem;
            line-height: 1.65;
            max-width: 500px;
            margin: 0 auto 1.2rem auto;
        }
        .wf-404-path {
            display: inline-block;
            background: rgba(212, 175, 55, 0.1);
            border: 1px solid rgba(212, 175, 55, 0.35);
            border-radius: 999px;
            padding: 0.3rem 1rem;
            font-size: 0.85rem;
            color: #CFC4B4;
            margin-bottom: 0.8rem;
        }
        .wf-404-path span {
            color: #F0CA5A;
            font-weight: 700;
        }
        </style>
        <div id="wf-404-marker" class="wf-404-wrap wf-blur-in">
            <div class="wf-404-code">404</div>
            <h2 class="wf-404-title">Lost in the Darkness</h2>
            __PATH_BADGE__
            <p class="wf-404-msg">
                The page you are looking for does not exist or may have moved.
                Return to Waqar Foodies or jump straight to our signature menu.
            </p>
        </div>
    """.replace("__PATH_BADGE__", path_badge)

    with st.container(key="notfound_page_wrap"):
        st.html(page_404_html)
        _, b_left, b_right, _ = st.columns([1.2, 1.3, 1.3, 1.2])
        with b_left:
            if st.button("Back to Home", key="err404_home", type="primary", use_container_width=True):
                st.session_state._missing_path = ""
                st.switch_page(home_page)
        with b_right:
            if st.button("Explore Menu", key="err404_menu", use_container_width=True):
                st.session_state._missing_path = ""
                st.switch_page(menu_page)


# -----------------------------------------------------------------------------
# Review & Bug Report Sections
# -----------------------------------------------------------------------------
def render_review_section(standalone: bool = False):
    st.html(
        """
        <div id="wf-review-anchor" class="wf-blur-in">
            <h2 class="wf-section-title">Submit a <span>Review</span></h2>
            <p class="wf-section-sub">Loved the crunch, smoke, and warmth? Your review goes live on our wall.</p>
        </div>
        """
    )
    _, center_col, _ = st.columns([1, 2.2, 1])
    with center_col:
        if st.session_state.pop("review_submitted_notice", False):
            st.success("Thank you. Your review is now featured in Voices After Darkness.")

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
                height=115,
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
                    reviews_store = get_live_reviews_store()
                    reviews_store.insert(0, {
                        "name": clean_name,
                        "stars": stars,
                        "text": clean_rev,
                    })
                    del reviews_store[20:]
                    st.session_state.review_submitted_notice = True
                    st.rerun()
                else:
                    st.error("Could not send review right now. Please try again shortly.")


def render_review_page():
    detach_home_listeners_js()
    with st.container(key="review_page_wrap"):
        render_review_section(standalone=True)


def render_bug_page():
    detach_home_listeners_js()
    with st.container(key="bug_page_wrap"):
        st.html(
            """
            <div class="wf-blur-in">
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
# Menu Page (/menu)
# -----------------------------------------------------------------------------
def render_menu_page():
    detach_home_listeners_js()
    with st.container(key="menu_page_wrap"):
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
                    card_html = """
                        <div class="wf-menu-card wf-blur-in">
                            __IMG__
                            <div class="wf-menu-title">__NAME__</div>
                            <div class="wf-menu-price">__PRICE__/- PKR</div>
                            <div class="wf-menu-desc">__DESC__</div>
                        </div>
                    """.replace("__IMG__", img_html).replace("__NAME__", item["name"]).replace("__PRICE__", str(item["price"])).replace("__DESC__", item["desc"])
                    st.html(card_html)
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
# Home Page (/) — 2D Multi-Directional Spatial Panning Experience
# -----------------------------------------------------------------------------
def render_home_page():
    # 0. Intro Video Overlay
    st.html(
        """
        <style>
        #wf-intro-overlay {
            position: fixed;
            inset: 0;
            width: 100vw;
            height: 100dvh;
            z-index: 999999;
            background: #0B0A09 !important;
            overflow: hidden;
            opacity: 1;
            transition: opacity 0.95s ease;
        }
        #wf-intro-overlay::after {
            content: "";
            position: absolute;
            inset: 0;
            z-index: 3;
            pointer-events: none;
            box-shadow: inset 0 0 70px 28px #0B0A09;
        }
        #wf-intro-overlay.wf-removed {
            display: none !important;
            pointer-events: none !important;
        }
        #wf-intro-video {
            position: absolute;
            inset: 0;
            width: 100vw;
            height: 100dvh;
            object-fit: cover;
            object-position: center center;
            transform: scale(1.16);
            opacity: 0;
            transition: opacity 1.0s ease;
            z-index: 2;
        }
        @media (max-width: 768px) {
            #wf-intro-video {
                object-fit: cover;
                object-position: center center;
                transform: scale(1.20);
            }
        }
        #wf-intro-skip {
            position: absolute;
            bottom: 28px;
            right: 28px;
            z-index: 6;
            background: rgba(18, 18, 18, 0.78);
            color: #F5EFE6;
            border: 1px solid rgba(212, 175, 55, 0.48);
            border-radius: 999px;
            padding: 8px 20px;
            font-weight: 600;
            font-size: 0.85rem;
            cursor: pointer;
        }
        #wf-intro-skip:hover {
            border-color: #D4AF37;
            color: #D4AF37;
        }
        </style>

        <div id="wf-intro-overlay">
            <video id="wf-intro-video" src="./app/static/intro.mp4" autoplay muted playsinline webkit-playsinline preload="auto"></video>
            <button id="wf-intro-skip" type="button">Skip</button>
        </div>

        <script>
        (function() {
            let tries = 0;
            function initIntro() {
                const overlay = document.getElementById('wf-intro-overlay');
                const vid = document.getElementById('wf-intro-video');
                const skipBtn = document.getElementById('wf-intro-skip');
                const navBar = document.querySelector('.st-key-navbar_wrap');
                const heroInner = document.querySelector('.wf-hero');

                if (!overlay || !vid) {
                    if (tries++ < 45) requestAnimationFrame(initIntro);
                    return;
                }

                if (window.__wfIntroDone) {
                    overlay.classList.add('wf-removed');
                    if (navBar) navBar.classList.remove('wf-page-hidden');
                    if (heroInner) heroInner.classList.remove('wf-page-hidden');
                    return;
                }

                if (navBar) navBar.classList.add('wf-page-hidden');
                if (heroInner) heroInner.classList.add('wf-page-hidden');

                let finished = false;

                function finishIntro() {
                    if (finished) return;
                    finished = true;
                    window.__wfIntroDone = true;
                    overlay.style.opacity = '0';

                    setTimeout(() => {
                        if (document.body.contains(overlay)) {
                            overlay.classList.add('wf-removed');
                        }
                    }, 980);

                    setTimeout(() => {
                        const nav = document.querySelector('.st-key-navbar_wrap');
                        const hero = document.querySelector('.wf-hero');
                        [nav, hero].forEach((el) => {
                            if (!el) return;
                            el.classList.remove('wf-page-hidden');
                            void el.offsetWidth;
                            el.classList.add('wf-blur-in');
                        });
                    }, 1950);
                }

                function startPlayback() {
                    vid.muted = true;
                    vid.setAttribute('muted', '');
                    vid.setAttribute('playsinline', '');
                    vid.style.opacity = '1';

                    const p = vid.play();
                    if (p && typeof p.catch === 'function') p.catch(() => {});
                }

                vid.addEventListener('loadedmetadata', startPlayback);
                vid.addEventListener('loadeddata', startPlayback);
                vid.addEventListener('canplay', startPlayback);

                vid.addEventListener('timeupdate', () => {
                    if (vid.duration && vid.duration - vid.currentTime <= 0.85) {
                        finishIntro();
                    }
                });

                vid.addEventListener('ended', finishIntro);
                vid.addEventListener('error', finishIntro);
                skipBtn.addEventListener('click', finishIntro);

                overlay.addEventListener('touchstart', () => {
                    if (vid.paused && !finished) startPlayback();
                }, { passive: true });

                vid.load();

                setTimeout(() => {
                    if (!finished && vid.readyState === 0) {
                        finishIntro();
                    } else if (!finished && vid.paused) {
                        startPlayback();
                    }
                }, 4200);
            }

            requestAnimationFrame(initIntro);
        })();
        </script>
        """,
        unsafe_allow_javascript=True,
    )

    # -------------------------------------------------------------------------
    # Room (0, 0): Hero Quote
    # -------------------------------------------------------------------------
    with st.container(key="panel_hero"):
        st.html(
            """
            <style>
            .wf-hero {
                text-align: center;
                padding: 1rem;
                display: flex;
                flex-direction: column;
                justify-content: center;
                align-items: center;
            }
            .wf-quote-card {
                position: relative;
                max-width: 960px;
                padding: 2.3rem 2.6rem 1.9rem 2.6rem;
                border-top: 1px solid rgba(212, 175, 55, 0.35);
                border-bottom: 1px solid rgba(212, 175, 55, 0.35);
                background: radial-gradient(circle at 50% 50%, rgba(212, 175, 55, 0.06), transparent 72%);
            }
            .wf-quote-mark-open,
            .wf-quote-mark-close {
                font-family: 'Cormorant Garamond', serif;
                font-style: italic;
                font-size: clamp(3.4rem, 6vw, 5.4rem);
                color: rgba(212, 175, 55, 0.55);
                line-height: 0.45;
                user-select: none;
            }
            .wf-quote-mark-open { margin-bottom: 0.75rem; display: block; text-align: left; }
            .wf-quote-mark-close { margin-top: 0.75rem; display: block; text-align: right; }
            .wf-hero-heading { color: #F5EFE6; line-height: 1.28; margin: 0 auto; font-weight: 400; }
            .wf-w-flavour {
                font-family: 'Great Vibes', cursive;
                font-size: clamp(3.6rem, 7.6vw, 6.4rem);
                font-weight: 400;
                color: #D4AF37;
                letter-spacing: 1px;
                text-shadow: 0 4px 28px rgba(212, 175, 55, 0.38);
                padding-right: 4px;
            }
            .wf-w-small {
                font-family: 'Cormorant Garamond', serif;
                font-size: clamp(1.3rem, 2.6vw, 2.15rem);
                font-weight: 300;
                color: #E6DAC8;
                font-style: italic;
                letter-spacing: 0.8px;
            }
            .wf-w-alive {
                font-family: 'Parisienne', cursive;
                font-size: clamp(2.4rem, 4.8vw, 3.9rem);
                font-weight: 400;
                color: #F5EFE6;
                letter-spacing: 0.8px;
                text-shadow: 0 2px 18px rgba(245, 239, 230, 0.22);
            }
            .wf-w-darkness {
                font-family: 'Great Vibes', cursive;
                font-size: clamp(3.5rem, 7.3vw, 6.1rem);
                font-weight: 400;
                letter-spacing: 1.2px;
                padding: 0 6px;
                background: linear-gradient(180deg, #FFF5DC 0%, #D4AF37 58%, #9A7418 100%);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                filter: drop-shadow(0 6px 24px rgba(212, 175, 55, 0.28));
            }
            .wf-quote-attr {
                margin-top: 1.1rem;
                font-family: 'Cormorant Garamond', serif;
                font-style: italic;
                font-size: 1rem;
                letter-spacing: 3.5px;
                text-transform: uppercase;
                color: #D4AF37;
                font-weight: 600;
            }
            .wf-dir-hint {
                margin-top: 2rem;
                font-size: 0.78rem;
                letter-spacing: 2.4px;
                text-transform: uppercase;
                color: rgba(245, 239, 230, 0.5);
            }
            @media (max-width: 640px) {
                .wf-quote-card { padding: 1.5rem 1rem 1.3rem 1rem; }
            }
            </style>
            <div class="wf-hero">
                <blockquote class="wf-quote-card">
                    <span class="wf-quote-mark-open">“</span>
                    <h1 class="wf-hero-heading">
                        <span class="wf-w-flavour">Flavour</span><span class="wf-w-small">, that comes</span>
                        <span class="wf-w-alive"> Alive </span>
                        <span class="wf-w-small">After </span>
                        <span class="wf-w-darkness">Darkness</span>
                    </h1>
                    <span class="wf-quote-mark-close">”</span>
                    <div class="wf-quote-attr">— Waqar Foodies</div>
                </blockquote>
                <div class="wf-dir-hint">&darr;</div>
            </div>
            """
        )

    # -------------------------------------------------------------------------
    # Room (0, 1): Full-Screen Burger Ingredient Showcase
    # -------------------------------------------------------------------------
    with st.container(key="panel_video"):
        st.html(
            """
            <style>
            #wf-fullscreen-stage {
                position: relative;
                width: 100vw;
                height: 100dvh;
                overflow: hidden;
                display: flex;
                align-items: center;
                justify-content: center;
                background: radial-gradient(circle at 50% 48%, #4F3814 0%, #17130D 65%, #0D0C0A 100%);
                transition: background 1.1s cubic-bezier(0.22, 1, 0.36, 1);
                touch-action: none;
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
                height: 100dvh;
                width: auto;
                max-width: 100vw;
                object-fit: contain;
                -webkit-mask-image: radial-gradient(ellipse 52% 68% at 50% 50%, #000 54%, rgba(0,0,0,0.45) 78%, transparent 100%);
                mask-image: radial-gradient(ellipse 52% 68% at 50% 50%, #000 54%, rgba(0,0,0,0.45) 78%, transparent 100%);
                opacity: 0.96;
                transition: opacity 0.18s ease;
            }
            .wf-side-grid {
                position: relative;
                z-index: 4;
                width: 100%;
                max-width: 1380px;
                padding: 76px 3.5vw 0 3.5vw;
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
            .wf-side-spacer { min-height: 10px; }
            .wf-source-label {
                font-size: 0.76rem;
                letter-spacing: 2.2px;
                text-transform: uppercase;
                color: #D4AF37;
                margin-bottom: 0.45rem;
                font-weight: 600;
            }
            .wf-side-subheader {
                font-family: 'Playfair Display', serif;
                font-size: clamp(1.45rem, 2.8vw, 2.7rem);
                color: #F5EFE6;
                line-height: 1.18;
                margin: 0;
                text-shadow: 0 4px 20px rgba(0, 0, 0, 0.85);
            }
            .wf-side-body {
                color: #EAE0D2;
                font-size: clamp(0.88rem, 1.25vw, 1.12rem);
                line-height: 1.65;
                margin: 0;
                text-shadow: 0 2px 14px rgba(0, 0, 0, 0.9);
            }
            @keyframes wfTextBlurIn {
                0% { opacity: 0; filter: blur(16px); transform: translateY(18px); }
                100% { opacity: 1; filter: blur(0px); transform: translateY(0); }
            }
            .wf-side-animate { animation: wfTextBlurIn 0.85s cubic-bezier(0.22, 1, 0.36, 1) forwards; }
            .wf-side-hidden { opacity: 0; filter: blur(14px); }
            .wf-stage-progress {
                position: absolute;
                right: 16px;
                top: 54%;
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
                #wf-fullscreen-stage {
                    flex-direction: column;
                    justify-content: space-between;
                    padding: 112px 1rem 56px 1rem;
                    box-sizing: border-box;
                }
                .wf-stage-visual-wrap {
                    position: relative;
                    inset: auto;
                    order: 2;
                    flex: 0 0 auto;
                    width: 100%;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    margin: 0.3rem 0;
                }
                #wf-burger-canvas-video {
                    width: 82vw;
                    max-width: 360px;
                    height: auto;
                    aspect-ratio: 1 / 1;
                    max-height: 38dvh;
                    object-fit: contain;
                    -webkit-mask-image: radial-gradient(circle at 50% 50%, #000 62%, transparent 98%);
                    mask-image: radial-gradient(circle at 50% 50%, #000 62%, transparent 98%);
                }
                .wf-side-grid { display: contents; }
                .wf-side-spacer { display: none; }
                .wf-side-left {
                    order: 1;
                    width: 92%;
                    text-align: center;
                    border: none;
                    border-bottom: 1px solid rgba(212, 175, 55, 0.35);
                    background: rgba(14, 13, 11, 0.6);
                    border-radius: 14px;
                    padding: 0.7rem 0.9rem;
                    z-index: 4;
                }
                .wf-side-right {
                    order: 3;
                    width: 92%;
                    text-align: center;
                    border: none;
                    border-top: 1px solid rgba(212, 175, 55, 0.35);
                    background: rgba(14, 13, 11, 0.6);
                    border-radius: 14px;
                    padding: 0.7rem 0.9rem;
                    z-index: 4;
                }
            }
            </style>

            <div id="wf-fullscreen-stage">
                <div class="wf-stage-visual-wrap">
                    <video id="wf-burger-canvas-video" src="./app/static/burger_prep.mp4" autoplay muted playsinline webkit-playsinline preload="auto"></video>
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
            """
        )

    # -------------------------------------------------------------------------
    # Room (1, 1): Order Now Spotlight
    # -------------------------------------------------------------------------
    with st.container(key="panel_cta"):
        st.html(
            """
            <style>
            .wf-cta-spotlight {
                text-align: center;
                max-width: 820px;
                margin: 0 auto 1.4rem auto;
            }
            .wf-cta-cards {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 1.4rem;
                margin-top: 1.4rem;
                margin-bottom: 1.6rem;
            }
            @media (max-width: 700px) {
                .wf-cta-cards { grid-template-columns: 1fr; gap: 0.9rem; }
            }
            .wf-cta-mini {
                background: linear-gradient(155deg, rgba(30, 28, 24, 0.95), rgba(18, 17, 15, 0.95));
                border: 1px solid rgba(212, 175, 55, 0.32);
                border-radius: 18px;
                padding: 1.3rem 1.4rem;
                text-align: left;
                box-shadow: 0 14px 36px rgba(0, 0, 0, 0.45);
            }
            .wf-cta-mini-title {
                font-family: 'Playfair Display', serif;
                font-size: 1.45rem;
                color: #F5EFE6;
                font-weight: 700;
            }
            .wf-cta-mini-price {
                color: #F0CA5A;
                font-weight: 700;
                font-size: 0.95rem;
                margin: 0.25rem 0 0.5rem 0;
            }
            .wf-cta-mini-desc {
                color: #CFC4B4;
                font-size: 0.9rem;
                line-height: 1.5;
            }
            </style>
            <div class="wf-cta-spotlight wf-room-anim">
                <h2 class="wf-section-title">Crafted For <span>Tonight</span></h2>
                <p class="wf-section-sub">Freshly seared over live charcoal and delivered piping hot after sundown.</p>
                <div class="wf-cta-cards">
                    <div class="wf-cta-mini">
                        <div class="wf-cta-mini-title">Tower Burger</div>
                        <div class="wf-cta-mini-price">500/- PKR</div>
                        <div class="wf-cta-mini-desc">Double flame-kissed beef patties, aged cheddar melt, garden greens, and house burger sauce on sesame brioche.</div>
                    </div>
                    <div class="wf-cta-mini">
                        <div class="wf-cta-mini-title">Chicken Paratha Roll</div>
                        <div class="wf-cta-mini-price">350/- PKR</div>
                        <div class="wf-cta-mini-desc">Crispy golden paratha layered with chargrilled chicken tikka, red onions, and signature mint-garlic crema.</div>
                    </div>
                </div>
            </div>
            """
        )
        _, cta_col, _ = st.columns([1.3, 1.2, 1.3])
        with cta_col:
            if st.button("Order Now", key="home_order_now", type="primary", use_container_width=True):
                st.switch_page(menu_page)

    # -------------------------------------------------------------------------
    # Room (1, 2): Voices After Darkness — Testimonials
    # -------------------------------------------------------------------------
    live_reviews = get_live_reviews_store()
    n_reviews = len(live_reviews)
    star_svg = (
        '<svg width="14" height="14" viewBox="0 0 24 24" fill="#D4AF37">'
        '<path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/>'
        '</svg>'
    )

    cards_html_parts = []
    for idx, rev in enumerate(live_reviews):
        diff = idx
        if diff > n_reviews // 2:
            diff -= n_reviews
        elif diff < -(n_reviews // 2):
            diff += n_reviews
        pos_attr = str(diff) if abs(diff) <= 2 else "hidden"

        safe_name = html.escape(str(rev["name"]))
        safe_text = html.escape(str(rev["text"]))
        stars_count = max(1, min(5, int(rev.get("stars", 5))))
        stars_html = f'<span class="wf-svg-stars">{star_svg * stars_count}</span>'

        cards_html_parts.append(
            '<div class="wf-t-card" data-idx="' + str(idx) + '" data-pos="' + pos_attr + '">'
            '<div class="wf-t-quote">“' + safe_text + '”</div>'
            '<div class="wf-t-author"><span>— ' + safe_name + '</span>' + stars_html + '</div>'
            '</div>'
        )

    cards_markup = "\n".join(cards_html_parts)

    with st.container(key="panel_testi"):
        testimonials_html = """
            <div class="wf-room-anim">
                <div id="wf-testimonials-anchor">
                    <h2 class="wf-section-title">Voices After <span>Darkness</span></h2>
                    <p class="wf-section-sub">Swipe inside to browse reviews, or outside to continue.</p>
                </div>

                <style>
                #wf-testi-box {
                    position: relative;
                    height: 380px;
                    max-width: 740px;
                    margin: 0 auto;
                    overflow: hidden;
                    border-radius: 24px;
                    background: radial-gradient(circle at 50% 50%, rgba(212, 175, 55, 0.08), #141311 78%);
                    border: 1px solid rgba(212, 175, 55, 0.22);
                    perspective: 900px;
                    user-select: none;
                    cursor: ns-resize;
                    touch-action: none;
                }
                #wf-testi-box::before,
                #wf-testi-box::after {
                    content: "";
                    position: absolute;
                    left: 0;
                    right: 0;
                    height: 70px;
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
                    padding: 1.3rem 1.6rem;
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
                .wf-t-card[data-pos="hidden"] {
                    transform: translate(-50%, 260%) scale(0.6);
                    opacity: 0;
                    pointer-events: none;
                    z-index: 0;
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

                <div id="wf-testi-box">
                    __CARDS_MARKUP__
                </div>
            </div>
        """.replace("__CARDS_MARKUP__", cards_markup)

        st.html(testimonials_html)

    # -------------------------------------------------------------------------
    # Room (0, 2): Submit Review
    # -------------------------------------------------------------------------
    with st.container(key="panel_review"):
        render_review_section(standalone=False)

    # -------------------------------------------------------------------------
    # 2D Spatial Camera & Lower-Left Compass HUD Controller
    # -------------------------------------------------------------------------
    st.html(
        """
        <style>
        #wf-spatial-hud {
            position: fixed;
            bottom: 18px;
            left: 22px;
            z-index: 950;
            display: flex;
            align-items: center;
            gap: 12px;
            background: rgba(18, 17, 15, 0.84);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(212, 175, 55, 0.34);
            border-radius: 16px;
            padding: 8px 14px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.55);
        }
        .wf-hud-grid {
            display: grid;
            grid-template-columns: repeat(2, 10px);
            grid-template-rows: repeat(3, 10px);
            gap: 5px;
        }
        .wf-hud-node {
            width: 10px;
            height: 10px;
            border-radius: 3px;
            background: rgba(245, 239, 230, 0.2);
            border: 1px solid rgba(212, 175, 55, 0.35);
            cursor: pointer;
            transition: all 0.35s ease;
        }
        .wf-hud-node.active {
            background: #D4AF37;
            box-shadow: 0 0 10px rgba(212, 175, 55, 0.75);
            transform: scale(1.2);
        }
        .wf-hud-meta {
            display: flex;
            flex-direction: column;
            line-height: 1.25;
        }
        .wf-hud-title {
            font-size: 0.74rem;
            font-weight: 700;
            color: #F5EFE6;
            letter-spacing: 0.8px;
            text-transform: uppercase;
        }
        .wf-hud-dir {
            font-size: 0.74rem;
            color: #D4AF37;
            letter-spacing: 0.8px;
        }
        @media (max-width: 640px) {
            #wf-spatial-hud {
                bottom: 10px;
                left: 12px;
                padding: 6px 10px;
            }
        }
        </style>

        <div id="wf-spatial-hud">
            <div class="wf-hud-grid" id="wf-hud-grid"></div>
            <div class="wf-hud-meta">
                <span class="wf-hud-title" id="wf-hud-title">Quote</span>
                <span class="wf-hud-dir" id="wf-hud-dir">Next &darr;</span>
            </div>
        </div>

        <script>
        (function() {
            let tries = 0;

            function detachAllSpatialListeners() {
                if (window.__wfStageWheelHandler) window.removeEventListener('wheel', window.__wfStageWheelHandler, true);
                if (window.__wfTouchStartHandler) window.removeEventListener('touchstart', window.__wfTouchStartHandler, true);
                if (window.__wfTouchMoveHandler) window.removeEventListener('touchmove', window.__wfTouchMoveHandler, true);
                if (window.__wfTouchEndHandler) window.removeEventListener('touchend', window.__wfTouchEndHandler, true);
                if (window.__wfTestiInterval) {
                    clearInterval(window.__wfTestiInterval);
                    window.__wfTestiInterval = null;
                }
            }

            window.__wfDetachSpatial = detachAllSpatialListeners;

            function initSpatialWorld() {
                const rooms = [
                    { sel: '.st-key-panel_hero',   col: 0, row: 0, title: 'Quote',        dir: 'Next \u2193' },
                    { sel: '.st-key-panel_video',  col: 0, row: 1, title: 'Craft',        dir: '\u2193  |  Next \u2192' },
                    { sel: '.st-key-panel_cta',    col: 1, row: 1, title: 'Signature',    dir: 'Next \u2193' },
                    { sel: '.st-key-panel_testi',  col: 1, row: 2, title: 'Testimonials', dir: 'Next \u2190' },
                    { sel: '.st-key-panel_review', col: 0, row: 2, title: 'Review',       dir: 'Back \u2191' }
                ];

                const panels = rooms.map(r => document.querySelector(r.sel));
                const stage = document.getElementById('wf-fullscreen-stage');
                const video = document.getElementById('wf-burger-canvas-video');
                const hud = document.getElementById('wf-spatial-hud');
                const hudGrid = document.getElementById('wf-hud-grid');
                const hudTitle = document.getElementById('wf-hud-title');
                const hudDir = document.getElementById('wf-hud-dir');

                if (panels.some(p => !p) || !stage || !video || !hud) {
                    if (tries++ < 45) requestAnimationFrame(initSpatialWorld);
                    return;
                }

                let activeRoom = typeof window.__wfActiveRoom === 'number' ? window.__wfActiveRoom : 0;
                let currentStep = typeof window.__wfVideoStep === 'number' ? window.__wfVideoStep : 0;
                let isBusy = false;
                let isVideoPrimed = false;
                let animFrame = null;

                // Build Lower-Left 2D Mini-Map HUD
                hudGrid.innerHTML = '';
                const hudNodes = [];
                rooms.forEach((r, idx) => {
                    const node = document.createElement('div');
                    node.className = 'wf-hud-node' + (idx === activeRoom ? ' active' : '');
                    node.style.gridColumn = String(r.col + 1);
                    node.style.gridRow = String(r.row + 1);
                    node.title = r.title;
                    node.addEventListener('click', () => {
                        if (!isBusy) goToRoom(idx);
                    });
                    hudGrid.appendChild(node);
                    hudNodes.push(node);
                });

                function triggerRoomFadeUp(panel) {
                    const animTargets = panel.querySelectorAll('.wf-room-anim, .wf-blur-in');
                    animTargets.forEach((el) => {
                        el.classList.remove('wf-blur-in');
                        void el.offsetWidth;
                        el.classList.add('wf-blur-in');
                    });
                }

                // Exact scene boundaries (each section plays only its own scene)
                const sections = [
                    {
                        startPct: 0.000,
                        endPct: 0.165, // Whole Bun preparation in Wheat Field
                        source: "Sunlit Golden Wheat Fields",
                        sub: "Toasted Sesame Brioche Bun",
                        body: "Harvested from golden wheat fields and baked pillowy-soft with toasted sesame seeds, splitting open in warm millstone mist.",
                        bg: "radial-gradient(circle at 50% 48%, #4F3814 0%, #17130D 65%, #0D0C0A 100%)"
                    },
                    {
                        startPct: 0.185,
                        endPct: 0.295, // Whole Vegetable splash in Garden
                        source: "Morning Dew Vegetable Farms",
                        sub: "Crisp Lettuce, Vine Tomatoes & Red Onions",
                        body: "Dew-fresh emerald lettuce, sun-ripened tomato slices, and sharp purple onion rings cascading straight from fertile garden soil.",
                        bg: "radial-gradient(circle at 50% 48%, #153D23 0%, #0E1711 65%, #0B0E0C 100%)"
                    },
                    {
                        startPct: 0.315,
                        endPct: 0.480, // Whole Milk splash -> Double Cheddar & Pickles
                        source: "Lush Green Dairy Pastures",
                        sub: "Creamy Double Cheddar & Crisp Pickles",
                        body: "Wholesome pasture milk churned into two rich, velvety cheddar slices, layered generously over tangy dill pickles and greens.",
                        bg: "radial-gradient(circle at 50% 48%, #2E3F19 0%, #15170F 65%, #0C0D0A 100%)"
                    },
                    {
                        startPct: 0.505,
                        endPct: 0.685, // Whole Double Beef Patties over Flames
                        source: "Twilight Wood-Fired Grill",
                        sub: "Double Charcoal-Seared Beef Patties",
                        body: "Two thick, hand-pressed beef patties seared at dusk over roaring hardwood flames—locking in smoky char and sizzling juices.",
                        bg: "radial-gradient(circle at 50% 48%, #521A0E 0%, #180E0D 65%, #0D0A0A 100%)"
                    },
                    {
                        startPct: 0.715,
                        endPct: 0.985, // Whole Assembly Burst -> Finished Tower Burger in Darkness
                        source: "Waqar Foodies — After Darkness",
                        sub: "The Signature Double Tower Burger",
                        body: "Crowned with crushed peppercorns, signature house burger sauce, and warm golden bokeh—crafted to come alive after darkness.",
                        bg: "radial-gradient(circle at 50% 48%, #36240B 0%, #12100D 65%, #0A0A09 100%)"
                    }
                ];

                const leftBox = document.getElementById('wf-left-text');
                const rightBox = document.getElementById('wf-right-text');
                const sourceEl = document.getElementById('wf-ing-source');
                const subEl = document.getElementById('wf-ing-sub');
                const bodyEl = document.getElementById('wf-ing-body');
                const dotsWrap = document.getElementById('wf-stage-dots');

                function primeMobileVideo() {
                    if (isVideoPrimed) return;
                    isVideoPrimed = true;
                    video.muted = true;
                    const p = video.play();
                    if (p && typeof p.then === 'function') {
                        p.then(() => {
                            if (activeRoom !== 1 && !isBusy) {
                                video.pause();
                                video.currentTime = 0;
                            }
                        }).catch(() => { isVideoPrimed = false; });
                    }
                }

                video.addEventListener('playing', function onFirstPlay() {
                    if (activeRoom !== 1 && !isBusy) {
                        video.pause();
                        video.currentTime = 0;
                    }
                    isVideoPrimed = true;
                    video.removeEventListener('playing', onFirstPlay);
                });

                video.load();
                primeMobileVideo();

                dotsWrap.innerHTML = "";
                sections.forEach((_, idx) => {
                    const dot = document.createElement('div');
                    dot.className = 'wf-prog-dot' + (idx === currentStep ? ' active' : '');
                    dot.addEventListener('click', () => {
                        if (!isBusy) goToVideoStep(idx);
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
                    }, 120);
                }

                // Plays ONLY the selected part's startPct -> endPct and slows gently to a stop (ease-out)
                function playPartWithSlowEaseOut(stepIdx) {
                    if (animFrame) cancelAnimationFrame(animFrame);

                    function beginPlay() {
                        const duration = video.duration;
                        if (!duration || isNaN(duration)) {
                            isBusy = false;
                            return;
                        }

                        const s = sections[stepIdx];
                        const startTime = Math.max(0, s.startPct * duration);
                        const endTime = Math.min(duration - 0.04, s.endPct * duration);
                        const span = Math.max(0.2, endTime - startTime);

                        // Brief cross-dissolve so the cut to the new part never flashes
                        video.style.opacity = '0.28';
                        video.pause();
                        video.currentTime = startTime;

                        setTimeout(() => {
                            video.style.opacity = '0.96';
                            video.muted = true;
                            video.playbackRate = 0.85;
                            video.play().catch(() => {});

                            let lastRateTick = performance.now();

                            function monitorPart(now) {
                                const cur = video.currentTime;
                                const progress = Math.max(0, Math.min(1, (cur - startTime) / span));

                                if (cur >= endTime - 0.015 || progress >= 0.995 || video.ended) {
                                    video.pause();
                                    video.currentTime = endTime;
                                    video.playbackRate = 0.85;
                                    isBusy = false;
                                    return;
                                }

                                // Smooth slow-motion deceleration (ease-out) during the final 45% of the part
                                if (progress >= 0.55 && now - lastRateTick >= 95) {
                                    const tail = (progress - 0.55) / 0.45;
                                    const easedRate = Math.max(0.16, 0.85 * Math.pow(1 - tail, 1.45));
                                    video.playbackRate = easedRate;
                                    lastRateTick = now;
                                }

                                animFrame = requestAnimationFrame(monitorPart);
                            }

                            animFrame = requestAnimationFrame(monitorPart);
                        }, 110);
                    }

                    if (video.readyState >= 1 && video.duration && !isNaN(video.duration)) {
                        beginPlay();
                    } else {
                        video.addEventListener('loadedmetadata', beginPlay, { once: true });
                    }
                }

                function goToVideoStep(nextIdx) {
                    if (nextIdx < 0 || nextIdx >= sections.length || nextIdx === currentStep) return;
                    isBusy = true;
                    currentStep = nextIdx;
                    window.__wfVideoStep = currentStep;
                    applySideText(currentStep);
                    playPartWithSlowEaseOut(currentStep);
                    setTimeout(() => { isBusy = false; }, 3400);
                }

                function applySpatialCamera(instant = false) {
                    const target = rooms[activeRoom];
                    panels.forEach((panel, i) => {
                        const r = rooms[i];
                        const dx = (r.col - target.col) * 100;
                        const dy = (r.row - target.row) * 100;

                        if (instant) {
                            panel.style.transition = 'none';
                        }
                        panel.style.transform = `translate3d(${dx}vw, ${dy}dvh, 0)`;
                        panel.style.opacity = (i === activeRoom) ? '1' : '0';
                        panel.style.pointerEvents = (i === activeRoom) ? 'auto' : 'none';

                        if (instant) {
                            void panel.offsetWidth;
                            panel.style.transition = '';
                        }
                    });

                    hudNodes.forEach((n, i) => n.classList.toggle('active', i === activeRoom));
                    if (hudTitle) hudTitle.textContent = target.title;
                    if (hudDir) hudDir.textContent = target.dir;
                }

                function goToRoom(nextRoom) {
                    if (nextRoom < 0 || nextRoom >= rooms.length || nextRoom === activeRoom) return;
                    isBusy = true;
                    const prevRoom = activeRoom;
                    activeRoom = nextRoom;
                    window.__wfActiveRoom = activeRoom;
                    applySpatialCamera(false);
                    triggerRoomFadeUp(panels[activeRoom]);

                    // Entering Craft room: auto-play the active part's full sequence with slow ease-out
                    if (activeRoom === 1) {
                        if (prevRoom === 0) {
                            currentStep = 0;
                            window.__wfVideoStep = 0;
                        }
                        applySideText(currentStep);
                        setTimeout(() => {
                            playPartWithSlowEaseOut(currentStep);
                        }, 420);
                        setTimeout(() => { isBusy = false; }, 3400);
                    } else {
                        if (animFrame) cancelAnimationFrame(animFrame);
                        video.pause();
                        setTimeout(() => { isBusy = false; }, 980);
                    }
                }

                // Testimonials Carousel Controller (Locked inside container — never scrolls page)
                const testiBox = document.getElementById('wf-testi-box');
                const cards = testiBox ? Array.from(testiBox.querySelectorAll('.wf-t-card')) : [];
                let activeTesti = 0;
                let autoTimer = null;
                let resumeTimeout = null;
                let boxLock = false;

                function layoutTesti() {
                    const n = cards.length;
                    cards.forEach((card, i) => {
                        let diff = i - activeTesti;
                        if (diff > Math.floor(n / 2)) diff -= n;
                        if (diff < -Math.floor(n / 2)) diff += n;
                        card.setAttribute('data-pos', Math.abs(diff) <= 2 ? String(diff) : 'hidden');
                    });
                }

                function stepTesti(dir) {
                    if (cards.length === 0) return;
                    activeTesti = (activeTesti + dir + cards.length) % cards.length;
                    layoutTesti();
                }

                function resetTestiAuto(pauseMs = 3400) {
                    if (autoTimer) clearInterval(autoTimer);
                    if (resumeTimeout) clearTimeout(resumeTimeout);
                    resumeTimeout = setTimeout(() => {
                        autoTimer = setInterval(() => stepTesti(1), 3400);
                        window.__wfTestiInterval = autoTimer;
                    }, pauseMs === 3400 ? 0 : pauseMs);
                }

                if (testiBox && cards.length > 0) {
                    cards.forEach((card, idx) => {
                        card.addEventListener('click', () => {
                            activeTesti = idx;
                            layoutTesti();
                            resetTestiAuto(6000);
                        });
                    });
                    layoutTesti();
                    if (window.__wfTestiInterval) clearInterval(window.__wfTestiInterval);
                    autoTimer = setInterval(() => stepTesti(1), 3400);
                    window.__wfTestiInterval = autoTimer;
                }

                function handleMasterScroll(dir, targetEl) {
                    if (isBusy) return;

                    if (activeRoom === 0) {
                        if (dir > 0) goToRoom(1);
                        return;
                    }

                    if (activeRoom === 1) {
                        if (dir > 0) {
                            if (currentStep < sections.length - 1) goToVideoStep(currentStep + 1);
                            else goToRoom(2);
                        } else {
                            if (currentStep > 0) goToVideoStep(currentStep - 1);
                            else goToRoom(0);
                        }
                        return;
                    }

                    if (activeRoom === 2) {
                        if (dir > 0) goToRoom(3);
                        else goToRoom(1);
                        return;
                    }

                    if (activeRoom === 3) {
                        if (testiBox && testiBox.contains(targetEl) && cards.length > 0) {
                            if (!boxLock) {
                                boxLock = true;
                                stepTesti(dir);
                                resetTestiAuto(5500);
                                setTimeout(() => { boxLock = false; }, 340);
                            }
                            return;
                        }
                        if (dir > 0) goToRoom(4);
                        else goToRoom(2);
                        return;
                    }

                    if (activeRoom === 4) {
                        const revPanel = panels[4];
                        if (dir < 0 && revPanel.scrollTop <= 4) {
                            goToRoom(3);
                        }
                    }
                }

                function isInteractiveOverlayOpen(target) {
                    return Boolean(
                        document.querySelector('[role="dialog"]:not([data-wf-ghost])') ||
                        document.querySelector('[data-testid="stPopoverBody"]:not([data-wf-ghost])') ||
                        (target && target.closest && target.closest('textarea, input, button, [role="dialog"], [data-testid="stPopoverBody"], .st-key-navbar_wrap'))
                    );
                }

                detachAllSpatialListeners();

                const navButtons = document.querySelectorAll('.st-key-navbar_wrap button');
                navButtons.forEach(btn => {
                    if (!btn.closest('.st-key-bag_popover')) {
                        btn.addEventListener('click', detachAllSpatialListeners, { once: true });
                    }
                });

                window.__wfStageWheelHandler = function(e) {
                    if (!document.body.contains(stage)) {
                        detachAllSpatialListeners();
                        return;
                    }
                    if (isInteractiveOverlayOpen(e.target)) return;
                    if (Math.abs(e.deltaY) < 4) return;

                    if (activeRoom === 4) {
                        const revPanel = panels[4];
                        const canScrollDown = revPanel.scrollTop + revPanel.clientHeight < revPanel.scrollHeight - 4;
                        if (e.deltaY > 0 && canScrollDown) return;
                        if (e.deltaY < 0 && revPanel.scrollTop > 4) return;
                    }

                    e.preventDefault();
                    handleMasterScroll(e.deltaY > 0 ? 1 : -1, e.target);
                };

                let touchStartY = null;
                let touchTriggered = false;

                window.__wfTouchStartHandler = function(e) {
                    if (!document.body.contains(stage)) {
                        detachAllSpatialListeners();
                        return;
                    }
                    if (isInteractiveOverlayOpen(e.target)) return;
                    primeMobileVideo();
                    if (e.touches.length !== 1) return;
                    touchStartY = e.touches[0].clientY;
                    touchTriggered = false;
                };

                window.__wfTouchMoveHandler = function(e) {
                    if (!document.body.contains(stage)) {
                        detachAllSpatialListeners();
                        return;
                    }
                    if (isInteractiveOverlayOpen(e.target)) return;

                    if (isBusy) {
                        e.preventDefault();
                        return;
                    }

                    if (touchStartY === null || e.touches.length !== 1) return;
                    const diff = touchStartY - e.touches[0].clientY;
                    if (Math.abs(diff) < 10) return;

                    if (activeRoom === 4) {
                        const revPanel = panels[4];
                        const canScrollDown = revPanel.scrollTop + revPanel.clientHeight < revPanel.scrollHeight - 4;
                        if (diff > 0 && canScrollDown) return;
                        if (diff < 0 && revPanel.scrollTop > 4) return;
                    }

                    e.preventDefault();
                    if (!touchTriggered && Math.abs(diff) >= 24) {
                        touchTriggered = true;
                        handleMasterScroll(diff > 0 ? 1 : -1, e.target);
                    }
                };

                window.__wfTouchEndHandler = function() {
                    touchStartY = null;
                    touchTriggered = false;
                };

                window.addEventListener('wheel', window.__wfStageWheelHandler, { passive: false, capture: true });
                window.addEventListener('touchstart', window.__wfTouchStartHandler, { passive: true, capture: true });
                window.addEventListener('touchmove', window.__wfTouchMoveHandler, { passive: false, capture: true });
                window.addEventListener('touchend', window.__wfTouchEndHandler, { passive: true, capture: true });

                applySpatialCamera(true);
                applySideText(currentStep);
            }

            requestAnimationFrame(initSpatialWorld);
        })();
        </script>
        """,
        unsafe_allow_javascript=True,
    )


# -----------------------------------------------------------------------------
# Dedicated URL Pages Setup (st.navigation) + 404 Route
# -----------------------------------------------------------------------------
home_page = st.Page(render_home_page, title="Waqar Foodies | Flavour After Darkness", default=True)
menu_page = st.Page(render_menu_page, title="Menu | Waqar Foodies", url_path="menu")
review_page = st.Page(render_review_page, title="Review | Waqar Foodies", url_path="review")
bug_page = st.Page(render_bug_page, title="Report a Bug | Waqar Foodies", url_path="report-a-bug")
not_found_page = st.Page(render_404_page, title="404 — Page Not Found | Waqar Foodies", url_path="404")

current_page = st.navigation(
    [home_page, menu_page, review_page, bug_page, not_found_page],
    position="hidden",
)

# Server-side catch for unknown initial URL paths -> switch to custom /404 page
if not st.session_state.get("_checked_initial_url", False):
    st.session_state._checked_initial_url = True
    try:
        raw_url = st.context.url or ""
        req_path = urlparse(raw_url).path.strip("/").lower()
    except Exception:
        req_path = ""
    if req_path and req_path not in {"menu", "review", "report-a-bug", "404"}:
        st.session_state._missing_path = "/" + req_path
        st.switch_page(not_found_page)


# -----------------------------------------------------------------------------
# Top Toolbar + Popover/Dialog Fade-Out Ghost Observer + 404 Modal Interceptor
# -----------------------------------------------------------------------------
def render_navbar(active_page):
    cart_items, total_qty, grand_total = get_cart_summary()

    st.html(
        """
        <script>
        (function() {
            if (window.__wfOverlayObserverAttached) return;
            window.__wfOverlayObserverAttached = true;

            let lastPopRect = null;
            let lastDlgRect = null;
            let popGhostActive = false;
            let dlgGhostActive = false;

            function handleBuiltInStreamlit404(dlgNode) {
                if (!dlgNode) return false;
                const txt = (dlgNode.textContent || "").toLowerCase();
                if (
                    (txt.includes("page not found") || txt.includes("no corresponding file")) &&
                    !dlgNode.querySelector('#wf-404-marker')
                ) {
                    dlgNode.style.display = 'none';
                    const closeBtn = dlgNode.querySelector('button');
                    if (closeBtn) closeBtn.click();
                    if (window.location.pathname !== '/404' && !window.__wf404Redirected) {
                        window.__wf404Redirected = true;
                        window.location.replace(window.location.origin + '/404');
                    }
                    return true;
                }
                return false;
            }

            function spawnPopoverGhost(popNode) {
                if (!popNode || popGhostActive) return;
                const r = popNode.getBoundingClientRect();
                if (r.width < 10 || r.height < 10) return;

                popGhostActive = true;
                const ghost = popNode.cloneNode(true);
                ghost.setAttribute('data-wf-ghost', '1');
                ghost.classList.add('wf-ghost-popover-out');
                ghost.style.left = r.left + 'px';
                ghost.style.top = r.top + 'px';
                ghost.style.width = r.width + 'px';
                ghost.style.height = r.height + 'px';
                document.body.appendChild(ghost);

                popNode.style.opacity = '0';

                setTimeout(() => {
                    ghost.remove();
                    popGhostActive = false;
                }, 320);
            }

            function spawnDialogGhost(dlgNode, rect) {
                const r = rect || (dlgNode ? dlgNode.getBoundingClientRect() : null);
                if (!dlgNode || !r || r.width < 10 || r.height < 10 || dlgGhostActive) return;

                dlgGhostActive = true;
                const ghost = dlgNode.cloneNode(true);
                ghost.setAttribute('data-wf-ghost', '1');
                ghost.classList.add('wf-ghost-dialog-out');
                ghost.style.left = r.left + 'px';
                ghost.style.top = r.top + 'px';
                ghost.style.width = r.width + 'px';
                ghost.style.height = r.height + 'px';
                document.body.appendChild(ghost);

                dlgNode.style.opacity = '0';

                setTimeout(() => {
                    ghost.remove();
                    dlgGhostActive = false;
                }, 340);
            }

            window.addEventListener('pointerdown', (e) => {
                const pop = document.querySelector('[data-testid="stPopoverBody"]:not([data-wf-ghost])');
                if (pop) {
                    lastPopRect = pop.getBoundingClientRect();
                    const clickedInsidePop = pop.contains(e.target);
                    const clickedOrderBtn = e.target.closest && e.target.closest('.st-key-basket_order_btn');
                    if (!clickedInsidePop || clickedOrderBtn) {
                        spawnPopoverGhost(pop);
                    }
                }

                const dlg = document.querySelector('[role="dialog"]:not([data-wf-ghost])');
                if (dlg) {
                    lastDlgRect = dlg.getBoundingClientRect();
                    const clickedCloseBtn = e.target.closest && e.target.closest('[role="dialog"] button[aria-label="Close"]');
                    if (!dlg.contains(e.target) || clickedCloseBtn) {
                        spawnDialogGhost(dlg, lastDlgRect);
                    }
                }
            }, true);

            window.addEventListener('keydown', (e) => {
                if (e.key !== 'Escape') return;
                const pop = document.querySelector('[data-testid="stPopoverBody"]:not([data-wf-ghost])');
                if (pop) spawnPopoverGhost(pop);
                const dlg = document.querySelector('[role="dialog"]:not([data-wf-ghost])');
                if (dlg) spawnDialogGhost(dlg, dlg.getBoundingClientRect());
            }, true);

            function findMatch(node, selector) {
                if (!node || node.nodeType !== 1) return null;
                if (node.matches && node.matches(selector)) return node;
                return node.querySelector ? node.querySelector(selector) : null;
            }

            const existingDlg = document.querySelector('[role="dialog"]:not([data-wf-ghost])');
            if (existingDlg) handleBuiltInStreamlit404(existingDlg);

            const observer = new MutationObserver((mutations) => {
                const livePop = document.querySelector('[data-testid="stPopoverBody"]:not([data-wf-ghost])');
                if (livePop) lastPopRect = livePop.getBoundingClientRect();
                const liveDlg = document.querySelector('[role="dialog"]:not([data-wf-ghost])');
                if (liveDlg) {
                    if (!handleBuiltInStreamlit404(liveDlg)) {
                        lastDlgRect = liveDlg.getBoundingClientRect();
                    }
                }

                for (const m of mutations) {
                    for (const added of m.addedNodes) {
                        const addDlg = findMatch(added, '[role="dialog"]');
                        if (addDlg) handleBuiltInStreamlit404(addDlg);
                    }

                    for (const removed of m.removedNodes) {
                        if (removed.getAttribute && removed.getAttribute('data-wf-ghost')) continue;

                        const remPop = findMatch(removed, '[data-testid="stPopoverBody"]');
                        if (remPop && !popGhostActive && lastPopRect) {
                            popGhostActive = true;
                            const ghost = remPop.cloneNode(true);
                            ghost.setAttribute('data-wf-ghost', '1');
                            ghost.classList.add('wf-ghost-popover-out');
                            ghost.style.left = lastPopRect.left + 'px';
                            ghost.style.top = lastPopRect.top + 'px';
                            ghost.style.width = lastPopRect.width + 'px';
                            ghost.style.height = lastPopRect.height + 'px';
                            document.body.appendChild(ghost);
                            lastPopRect = null;
                            setTimeout(() => { ghost.remove(); popGhostActive = false; }, 320);
                        }

                        const remDlg = findMatch(removed, '[role="dialog"]');
                        if (remDlg && !dlgGhostActive && lastDlgRect) {
                            const txt = (remDlg.textContent || "").toLowerCase();
                            if (txt.includes("page not found") || txt.includes("no corresponding file")) {
                                lastDlgRect = null;
                                continue;
                            }
                            dlgGhostActive = true;
                            const ghost = remDlg.cloneNode(true);
                            ghost.setAttribute('data-wf-ghost', '1');
                            ghost.classList.add('wf-ghost-dialog-out');
                            ghost.style.left = lastDlgRect.left + 'px';
                            ghost.style.top = lastDlgRect.top + 'px';
                            ghost.style.width = lastDlgRect.width + 'px';
                            ghost.style.height = lastDlgRect.height + 'px';
                            document.body.appendChild(ghost);
                            lastDlgRect = null;
                            setTimeout(() => { ghost.remove(); dlgGhostActive = false; }, 340);
                        }
                    }
                }
            });

            observer.observe(document.body, { childList: true, subtree: true });
        })();
        </script>
        """,
        unsafe_allow_javascript=True,
    )

    with st.container(key="navbar_wrap"):
        col_brand, col_home, col_menu, col_review, col_bug, col_bag = st.columns(
            [2.6, 0.78, 0.78, 0.85, 1.18, 0.6], vertical_alignment="center"
        )

        with col_brand:
            logo_exists = Path("static/Logo.png").exists()
            logo_html = (
                '<img src="./app/static/Logo.png" class="wf-brand-logo" alt="Waqar Foodies Logo" />'
                if logo_exists
                else ""
            )
            st.html(
                '<div class="wf-brand-wrap">'
                + logo_html
                + '<span class="wf-brand-name">Waqar Foodies</span></div>'
            )

        with col_home:
            if st.button(
                "Home",
                key="nav_home",
                type="primary" if active_page == home_page else "secondary",
                use_container_width=True,
            ):
                st.switch_page(home_page)

        with col_menu:
            if st.button(
                "Menu",
                key="nav_menu",
                type="primary" if active_page == menu_page else "secondary",
                use_container_width=True,
            ):
                st.switch_page(menu_page)

        with col_review:
            if st.button(
                "Review",
                key="nav_review",
                type="primary" if active_page == review_page else "secondary",
                use_container_width=True,
            ):
                st.switch_page(review_page)

        with col_bug:
            if st.button(
                "Report a bug",
                key="nav_bug",
                type="primary" if active_page == bug_page else "secondary",
                use_container_width=True,
            ):
                st.switch_page(bug_page)

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


# Render Dialogs, Fixed Navbar, and Active URL Page
if st.session_state.confirmed_order_id:
    show_confirmation_dialog(st.session_state.confirmed_order_id)
elif st.session_state.open_checkout_modal:
    st.session_state.open_checkout_modal = False
    show_checkout_dialog()

render_navbar(current_page)
current_page.run()
