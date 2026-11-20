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
# Page Config & Initialization
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Waqar Foodies | Flavour After Darkness",
    page_icon="🍔",
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
        "emoji": "🍔",
        "desc": "Charcoal-seared double beef patty, melted aged cheddar, crisp greens, pickles, and signature burger sauce on toasted sesame brioche.",
    },
    "paratha_roll": {
        "id": "paratha_roll",
        "name": "Chicken Paratha Roll",
        "price": 350,
        "image": "static/paratha_roll.png",
        "emoji": "🌯",
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
        st.warning("Your basket is empty. Add an item from the Menu first!")
        if st.button("Go to Menu", type="primary"):
            st.session_state.page = "Menu"
            st.rerun()
        return

    st.markdown("#### 🧾 Order Summary")
    for item in cart_items:
        st.write(f"• **{item['name']}** × {item['qty']} — `PKR {item['price'] * item['qty']:,}/-`")
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
                <div style="font-weight:700; color:#F0CA5A; margin-bottom:4px;">📱 JazzCash Transfer Details</div>
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

    if st.button("Confirm Order", type="primary", use_container_width=True):
        allowed, wait_sec = check_rate_limit("order_submit", cooldown_seconds=20)
        if not allowed:
            st.error(f"Please wait {wait_sec}s before placing another order.")
            return

        clean_name = sanitize_text(name_input, max_len=80)
        clean_addr = sanitize_text(address_input, max_len=250)
        valid_phone, clean_phone = validate_phone(phone_input)

        if len(clean_name) < 2:
            st.error("Please enter a valid name.")
            return
        if len(clean_addr) < 8:
            st.error("Please enter a complete delivery address.")
            return
        if not valid_phone:
            st.error("Please enter a valid phone number (e.g. 03001234567).")
            return

        receipt_bytes = None
        receipt_name = None
        if payment_method == "Online (JazzCash)":
            ok_img, receipt_bytes, receipt_name, img_err = validate_and_clean_receipt(uploaded_receipt)
            if not ok_img:
                st.error(img_err)
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
            st.error("Unable to submit order right now. Please try again shortly.")
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


@st.dialog("Order Confirmed!")
def show_confirmation_dialog(order_id: str):
    st.html(
        f"""
        <div style="text-align:center;">
            <div style="font-size:2.6rem;">✨🍔✨</div>
            <div style="color:#CFC4B4; margin-top:4px;">Your Order ID is</div>
            <div class="wf-order-id-box">
                <div class="wf-order-id-code" id="wf-order-id-text">{order_id}</div>
            </div>
            <button id="wf-copy-btn"
                style="background:linear-gradient(135deg,#D4AF37,#B88E24); color:#121212;
                       border:none; border-radius:999px; padding:8px 20px; font-weight:700;
                       cursor:pointer; margin-bottom:12px;">
                📋 Copy Order ID
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
                    document.getElementById('wf-copy-status').textContent = "Select & copy the ID above.";
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
# Top Toolbar (Logo Left + Menu / Review / Report a bug + Top-Right Basket)
# -----------------------------------------------------------------------------
def render_navbar():
    cart_items, total_qty, grand_total = get_cart_summary()

    col_brand, col_menu, col_review, col_bug, col_basket = st.columns(
        [2.6, 1.0, 1.0, 1.3, 1.4], vertical_alignment="center"
    )

    with col_brand:
        logo_exists = Path("static/Logo.png").exists()
        logo_html = (
            '<img src="./app/static/Logo.png" class="wf-brand-logo" alt="Waqar Foodies Logo" />'
            if logo_exists
            else '<span style="font-size:1.8rem;">🔥</span>'
        )
        c_logo, c_home = st.columns([3.5, 1.2], vertical_alignment="center")
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

    with col_basket:
        basket_label = f"🛒 Basket ({total_qty})"
        with st.popover(basket_label, use_container_width=True):
            st.markdown("### 🛒 Your Basket")
            if not cart_items:
                st.caption("Your basket is currently empty.")
            else:
                for item in cart_items:
                    r1, r2, r3, r4 = st.columns([2.5, 0.7, 0.7, 1.4], vertical_alignment="center")
                    with r1:
                        st.markdown(f"**{item['name']}**")
                        st.caption(f"PKR {item['price']:,} × {item['qty']}")
                    with r2:
                        if st.button("−", key=f"dec_{item['id']}"):
                            update_cart_qty(item["id"], -1)
                            st.rerun()
                    with r3:
                        if st.button("+", key=f"inc_{item['id']}"):
                            update_cart_qty(item["id"], +1)
                            st.rerun()
                    with r4:
                        st.markdown(f"**{item['price'] * item['qty']:,}**")

                st.divider()
                st.markdown(f"#### Grand Total: :orange[PKR {grand_total:,}/-]")
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
        <div style="margin-top: 2.5rem;">
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
                allowed, wait_sec = check_rate_limit("review_submit", cooldown_seconds=15)
                if not allowed:
                    st.warning(f"Please wait {wait_sec}s before submitting another review.")
                    return
                if rating_idx is None:
                    st.error("Please select a star rating (1 to 5 stars).")
                    return
                clean_rev = sanitize_text(review_text, max_len=800)
                clean_name = sanitize_text(reviewer_name, max_len=60) or "Guest"
                if len(clean_rev) < 5:
                    st.error("Please write at least a few words in your review.")
                    return

                stars = rating_idx + 1
                with st.spinner("Submitting review..."):
                    ok = send_review_webhook(stars=stars, review_text=clean_rev, reviewer_name=clean_name)
                if ok:
                    st.success("Thank you! Your review has been sent to Waqar Foodies.")
                else:
                    st.error("Could not send review right now. Please try again shortly.")


def render_bug_page():
    st.html(
        """
        <div style="margin-top: 1.5rem;">
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
                allowed, wait_sec = check_rate_limit("bug_submit", cooldown_seconds=15)
                if not allowed:
                    st.warning(f"Please wait {wait_sec}s before submitting another report.")
                    return
                clean_bug = sanitize_text(bug_text, max_len=1000)
                clean_name = sanitize_text(reporter_name, max_len=60) or "Anonymous"
                if len(clean_bug) < 8:
                    st.error("Please provide a clear description of the bug.")
                    return

                with st.spinner("Sending bug report..."):
                    ok = send_bug_webhook(bug_text=clean_bug, reporter_name=clean_name)
                if ok:
                    st.success("Bug report received! Thank you for helping improve Waqar Foodies.")
                else:
                    st.error("Could not send bug report right now. Please try again later.")


# -----------------------------------------------------------------------------
# Menu Page
# -----------------------------------------------------------------------------
def render_menu_page():
    st.html(
        """
        <div>
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
                    else f'<div class="wf-menu-placeholder">{item["emoji"]}</div>'
                )
                st.html(
                    f"""
                    <div class="wf-menu-card">
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
                        st.toast(f"Added {item['name']} to your basket!", icon="🛒")
                        st.rerun()


# -----------------------------------------------------------------------------
# Home Page (Intro Overlay -> Blur-In -> Hero -> Scroll Video -> Testimonials -> Review)
# -----------------------------------------------------------------------------
def render_home_page():
    # 1. Intro Video Fade-In / Fade-Out + Page Blur-In
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
        #wf-intro-overlay.wf-hidden {
            display: none !important;
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
            background: rgba(18, 18, 18, 0.75);
            color: #F5EFE6;
            border: 1px solid rgba(212, 175, 55, 0.5);
            border-radius: 999px;
            padding: 8px 18px;
            font-weight: 600;
            cursor: pointer;
            z-index: 2;
        }
        #wf-intro-skip:hover {
            border-color: #D4AF37;
            color: #D4AF37;
        }
        </style>

        <div id="wf-intro-overlay" class="wf-hidden">
            <video id="wf-intro-video" autoplay muted playsinline preload="auto">
                <source src="./app/static/intro.mp4" type="video/mp4" />
            </video>
            <button id="wf-intro-skip" type="button">Skip Intro →</button>
        </div>

        <script>
        (function() {
            const overlay = document.getElementById('wf-intro-overlay');
            const vid = document.getElementById('wf-intro-video');
            const skipBtn = document.getElementById('wf-intro-skip');
            const appRoot = document.querySelector('[data-testid="stAppViewContainer"]');

            if (sessionStorage.getItem('wf_intro_done') === '1') {
                return;
            }

            overlay.classList.remove('wf-hidden');
            let finished = false;

            function finishIntro() {
                if (finished) return;
                finished = true;
                sessionStorage.setItem('wf_intro_done', '1');
                overlay.style.opacity = '0';
                if (appRoot) {
                    appRoot.classList.add('wf-blur-in');
                }
                setTimeout(() => {
                    overlay.classList.add('wf-hidden');
                }, 1050);
            }

            vid.addEventListener('canplay', () => {
                vid.style.opacity = '1';
                vid.play().catch(() => finishIntro());
            });

            vid.addEventListener('timeupdate', () => {
                if (vid.duration && vid.duration - vid.currentTime <= 0.9) {
                    finishIntro();
                }
            });

            vid.addEventListener('ended', finishIntro);
            vid.addEventListener('error', finishIntro);
            skipBtn.addEventListener('click', finishIntro);

            setTimeout(() => {
                if (vid.readyState < 2) finishIntro();
                else vid.style.opacity = '1';
            }, 2500);
        })();
        </script>
        """,
        unsafe_allow_javascript=True,
    )

    # 2. Stylish Hero Header: "Flavour, that comes Alive After Darkness"
    st.html(
        """
        <style>
        .wf-hero {
            text-align: center;
            padding: 1.8rem 1rem 2.4rem 1rem;
        }
        .wf-hero-kicker {
            display: inline-block;
            color: #D4AF37;
            border: 1px solid rgba(212, 175, 55, 0.35);
            background: rgba(212, 175, 55, 0.08);
            border-radius: 999px;
            padding: 0.3rem 1rem;
            font-size: 0.82rem;
            letter-spacing: 2px;
            text-transform: uppercase;
            margin-bottom: 1.1rem;
        }
        .wf-hero-heading {
            font-family: 'Playfair Display', serif;
            color: #F5EFE6;
            line-height: 1.15;
            margin: 0 auto;
            max-width: 920px;
        }
        .wf-w-flavour {
            font-family: 'Lobster', cursive;
            font-size: clamp(3.2rem, 6.5vw, 5.4rem);
            color: #D4AF37;
            text-shadow: 0 4px 24px rgba(212, 175, 55, 0.35);
        }
        .wf-w-small {
            font-size: clamp(1.3rem, 2.5vw, 2rem);
            font-weight: 400;
            color: #E6DAC8;
            font-style: italic;
        }
        .wf-w-alive {
            font-size: clamp(2.1rem, 4vw, 3.2rem);
            font-weight: 800;
            color: #F5EFE6;
            letter-spacing: 1px;
        }
        .wf-w-darkness {
            font-size: clamp(3.1rem, 6.2vw, 5.1rem);
            font-weight: 900;
            background: linear-gradient(180deg, #FFF5DC 0%, #D4AF37 55%, #8C6A15 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            filter: drop-shadow(0 6px 24px rgba(212, 175, 55, 0.25));
        }
        </style>
        <div class="wf-hero">
            <div class="wf-hero-kicker">Late-Night Artisan Cafe</div>
            <h1 class="wf-hero-heading">
                <span class="wf-w-flavour">Flavour</span><span class="wf-w-small">, that comes</span>
                <span class="wf-w-alive"> Alive </span>
                <span class="wf-w-small">After </span>
                <span class="wf-w-darkness">Darkness</span>
            </h1>
        </div>
        """
    )

    # 3. Scroll-Controlled Burger Video Animation (calibrated to 00:00 - 00:09 frames)
    st.html(
        """
        <style>
        #wf-story-stage {
            position: relative;
            border-radius: 26px;
            border: 1px solid rgba(212, 175, 55, 0.28);
            padding: 2.2rem;
            min-height: 540px;
            display: grid;
            grid-template-columns: 1.15fr 1fr;
            gap: 2rem;
            align-items: center;
            overflow: hidden;
            transition: background 0.9s cubic-bezier(0.22, 1, 0.36, 1), border-color 0.6s ease;
            background: radial-gradient(circle at 24% 30%, #4A3514 0%, #16130E 74%);
            box-shadow: 0 24px 60px rgba(0, 0, 0, 0.55);
        }
        @media (max-width: 860px) {
            #wf-story-stage {
                grid-template-columns: 1fr;
                padding: 1.4rem;
            }
        }
        .wf-video-frame {
            position: relative;
            border-radius: 18px;
            overflow: hidden;
            border: 1px solid rgba(212, 175, 55, 0.35);
            background: #0B0B0B;
            aspect-ratio: 1 / 1;
            max-height: 480px;
            margin: 0 auto;
            width: 100%;
            box-shadow: 0 14px 36px rgba(0, 0, 0, 0.6);
        }
        #wf-burger-video {
            width: 100%;
            height: 100%;
            object-fit: cover;
            display: block;
        }
        .wf-video-badge {
            position: absolute;
            top: 12px;
            left: 12px;
            background: rgba(18, 18, 18, 0.78);
            border: 1px solid rgba(212, 175, 55, 0.4);
            color: #F0CA5A;
            padding: 4px 12px;
            border-radius: 999px;
            font-size: 0.76rem;
            letter-spacing: 1px;
            text-transform: uppercase;
        }
        .wf-sound-btn {
            position: absolute;
            top: 12px;
            right: 12px;
            background: rgba(18, 18, 18, 0.78);
            border: 1px solid rgba(212, 175, 55, 0.45);
            color: #F5EFE6;
            padding: 4px 11px;
            border-radius: 999px;
            font-size: 0.76rem;
            cursor: pointer;
            transition: all 0.25s ease;
        }
        .wf-sound-btn:hover {
            border-color: #D4AF37;
            color: #F0CA5A;
        }
        .wf-ingredient-panel {
            display: flex;
            flex-direction: column;
            justify-content: center;
            gap: 0.85rem;
            transition: opacity 0.4s ease, transform 0.4s ease;
        }
        .wf-ingredient-panel.wf-fade {
            opacity: 0.25;
            transform: translateY(10px);
        }
        .wf-source-pill {
            display: inline-block;
            width: fit-content;
            font-size: 0.8rem;
            text-transform: uppercase;
            letter-spacing: 1.8px;
            color: #D4AF37;
            border-bottom: 1px solid rgba(212, 175, 55, 0.45);
            padding-bottom: 4px;
        }
        .wf-ing-sub {
            font-family: 'Playfair Display', serif;
            font-size: clamp(1.7rem, 2.8vw, 2.35rem);
            color: #F5EFE6;
            margin: 0;
            line-height: 1.2;
        }
        .wf-ing-body {
            color: #D8CEC0;
            font-size: 1.03rem;
            line-height: 1.65;
            margin: 0;
        }
        .wf-story-controls {
            display: flex;
            align-items: center;
            gap: 10px;
            margin-top: 1rem;
            flex-wrap: wrap;
        }
        .wf-step-dot {
            width: 11px;
            height: 11px;
            border-radius: 50%;
            background: rgba(245, 239, 230, 0.22);
            border: 1px solid rgba(212, 175, 55, 0.4);
            cursor: pointer;
            transition: all 0.3s ease;
        }
        .wf-step-dot.active {
            width: 30px;
            border-radius: 999px;
            background: #D4AF37;
        }
        .wf-step-btn {
            background: rgba(212, 175, 55, 0.14);
            color: #F0CA5A;
            border: 1px solid rgba(212, 175, 55, 0.45);
            border-radius: 999px;
            padding: 6px 14px;
            font-size: 0.82rem;
            font-weight: 600;
            cursor: pointer;
        }
        .wf-step-btn:hover {
            background: #D4AF37;
            color: #121212;
        }
        .wf-scroll-hint {
            font-size: 0.82rem;
            color: #B5AA99;
            margin-left: auto;
        }
        </style>

        <div id="wf-story-stage">
            <div class="wf-video-frame">
                <video id="wf-burger-video" muted playsinline preload="auto">
                    <source src="./app/static/burger_prep.mp4" type="video/mp4" />
                </video>
                <div class="wf-video-badge" id="wf-step-badge">Chapter 1 / 5</div>
                <button class="wf-sound-btn" id="wf-sound-toggle" type="button">🔇 Muted</button>
            </div>

            <div class="wf-ingredient-panel" id="wf-ing-panel">
                <div class="wf-source-pill" id="wf-ing-source">Source: Sunlit Golden Wheat Fields</div>
                <h2 class="wf-ing-sub" id="wf-ing-sub">Toasted Sesame Brioche Bun</h2>
                <p class="wf-ing-body" id="wf-ing-body">
                    Harvested from golden wheat fields and baked pillowy-soft with toasted sesame seeds, splitting open in a cloud of warm millstone mist.
                </p>

                <div class="wf-story-controls">
                    <div id="wf-dots" style="display:flex; gap:8px; align-items:center;"></div>
                    <button class="wf-step-btn" id="wf-prev-step" type="button">← Prev</button>
                    <button class="wf-step-btn" id="wf-next-step" type="button">Next Ingredient →</button>
                    <span class="wf-scroll-hint" id="wf-scroll-hint">Scroll over stage to animate ↑↓</span>
                </div>
            </div>
        </div>

        <script>
        (function() {
            const stage = document.getElementById('wf-story-stage');
            const video = document.getElementById('wf-burger-video');
            const panel = document.getElementById('wf-ing-panel');
            const sourceEl = document.getElementById('wf-ing-source');
            const subEl = document.getElementById('wf-ing-sub');
            const bodyEl = document.getElementById('wf-ing-body');
            const badgeEl = document.getElementById('wf-step-badge');
            const dotsEl = document.getElementById('wf-dots');
            const hintEl = document.getElementById('wf-scroll-hint');
            const soundBtn = document.getElementById('wf-sound-toggle');

            const sections = [
                {
                    pct: 0.00, // 00:00 - 00:01 (Wheat field & sesame bun in flour mist)
                    source: "Source: Sunlit Golden Wheat Fields",
                    sub: "Toasted Sesame Brioche Bun",
                    body: "Harvested from golden wheat fields and baked pillowy-soft with toasted sesame seeds, splitting open in a cloud of warm millstone mist.",
                    bg: "radial-gradient(circle at 24% 30%, #4A3514 0%, #16130E 74%)"
                },
                {
                    pct: 0.23, // ~00:02 (Organic garden soil, lettuce, red tomatoes & onion rings)
                    source: "Source: Morning Dew Vegetable Farms",
                    sub: "Crisp Lettuce, Vine Tomatoes & Red Onions",
                    body: "Dew-fresh emerald lettuce, sun-ripened tomato slices, and sharp purple onion rings cascading straight from fertile garden soil.",
                    bg: "radial-gradient(circle at 25% 32%, #133620 0%, #0F1410 74%)"
                },
                {
                    pct: 0.43, // ~00:03 - 00:04 (Cow pastures, milk splash & double cheddar + pickles)
                    source: "Source: Lush Green Dairy Pastures",
                    sub: "Creamy Double Cheddar & Crisp Pickles",
                    body: "Wholesome pasture milk churned into two rich, velvety cheddar slices, layered generously over tangy dill pickles and fresh greens.",
                    bg: "radial-gradient(circle at 28% 30%, #263818 0%, #15140F 74%)"
                },
                {
                    pct: 0.64, // ~00:05 - 00:06 (Twilight fire pit & sizzling double beef patties)
                    source: "Source: Twilight Wood-Fired Grill",
                    sub: "Double Charcoal-Seared Beef Patties",
                    body: "Two thick, hand-pressed beef patties seared at dusk over roaring hardwood flames—locking in smoky char and sizzling juices.",
                    bg: "radial-gradient(circle at 26% 36%, #4A190E 0%, #130F0F 74%)"
                },
                {
                    pct: 0.98, // ~00:07 - 00:09 (Spice burst into final Tower Burger in glowing darkness)
                    source: "Source: Waqar Foodies — After Darkness",
                    sub: "The Signature Double Tower Burger",
                    body: "Crowned with crushed peppercorns, signature house burger sauce, and warm golden bokeh—crafted to come alive after darkness.",
                    bg: "radial-gradient(circle at 50% 45%, #30210B 0%, #100F0E 76%)"
                }
            ];

            let currentStep = 0;
            let isTransitioning = false;
            let animFrame = null;

            soundBtn.addEventListener('click', () => {
                video.muted = !video.muted;
                soundBtn.textContent = video.muted ? "🔇 Muted" : "🔊 Sound On";
            });

            sections.forEach((_, idx) => {
                const dot = document.createElement('div');
                dot.className = 'wf-step-dot' + (idx === 0 ? ' active' : '');
                dot.addEventListener('click', () => {
                    if (!isTransitioning) goToStep(idx);
                });
                dotsEl.appendChild(dot);
            });

            function updateUI(stepIdx) {
                const s = sections[stepIdx];
                stage.style.background = s.bg;
                badgeEl.textContent = `Chapter ${stepIdx + 1} / ${sections.length}`;
                panel.classList.add('wf-fade');
                setTimeout(() => {
                    sourceEl.textContent = s.source;
                    subEl.textContent = s.sub;
                    bodyEl.textContent = s.body;
                    panel.classList.remove('wf-fade');
                }, 180);

                Array.from(dotsEl.children).forEach((d, i) => {
                    d.classList.toggle('active', i === stepIdx);
                });

                hintEl.textContent = stepIdx === sections.length - 1
                    ? "Video complete — scroll down to Order Now ↓"
                    : "Scroll over stage to animate ↑↓";
            }

            function easeInOutCubic(t) {
                return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
            }

            function animateVideoTo(targetPct) {
                if (animFrame) cancelAnimationFrame(animFrame);
                const duration = video.duration;
                if (!duration || isNaN(duration)) {
                    isTransitioning = false;
                    return;
                }

                const startTime = video.currentTime;
                const endTime = Math.min(duration - 0.05, Math.max(0, targetPct * duration));
                const distance = endTime - startTime;

                if (Math.abs(distance) < 0.04) {
                    video.pause();
                    isTransitioning = false;
                    return;
                }

                const animDurationMs = Math.max(900, Math.min(1550, Math.abs(distance) * 520));
                const startClock = performance.now();
                const goingForward = distance > 0;

                if (goingForward) {
                    video.playbackRate = 0.35;
                    video.play().catch(() => {});
                } else {
                    video.pause();
                }

                function step(now) {
                    const elapsed = now - startClock;
                    const progress = Math.min(1, elapsed / animDurationMs);
                    const eased = easeInOutCubic(progress);

                    if (goingForward && !video.paused) {
                        const speedBell = Math.sin(progress * Math.PI);
                        const avgRate = distance / (animDurationMs / 1000);
                        video.playbackRate = Math.min(2.6, Math.max(0.22, avgRate * (0.35 + 1.15 * speedBell)));

                        if (progress >= 1 || video.currentTime >= endTime) {
                            video.pause();
                            video.currentTime = endTime;
                            isTransitioning = false;
                            return;
                        }
                    } else {
                        video.currentTime = startTime + distance * eased;
                        if (progress >= 1) {
                            video.pause();
                            video.currentTime = endTime;
                            isTransitioning = false;
                            return;
                        }
                    }

                    animFrame = requestAnimationFrame(step);
                }

                animFrame = requestAnimationFrame(step);
            }

            function goToStep(nextIdx) {
                if (nextIdx < 0 || nextIdx >= sections.length || nextIdx === currentStep) return;
                isTransitioning = true;
                currentStep = nextIdx;
                updateUI(currentStep);
                animateVideoTo(sections[currentStep].pct);
                setTimeout(() => { isTransitioning = false; }, 1150);
            }

            stage.addEventListener('wheel', (e) => {
                if (Math.abs(e.deltaY) < 8) return;
                if (e.deltaY > 0 && currentStep < sections.length - 1) {
                    e.preventDefault();
                    if (!isTransitioning) goToStep(currentStep + 1);
                } else if (e.deltaY < 0 && currentStep > 0) {
                    e.preventDefault();
                    if (!isTransitioning) goToStep(currentStep - 1);
                }
            }, { passive: false });

            let touchStartY = null;
            stage.addEventListener('touchstart', (e) => {
                touchStartY = e.touches[0].clientY;
            }, { passive: true });
            stage.addEventListener('touchend', (e) => {
                if (touchStartY === null) return;
                const diff = touchStartY - e.changedTouches[0].clientY;
                touchStartY = null;
                if (Math.abs(diff) < 35 || isTransitioning) return;
                if (diff > 0 && currentStep < sections.length - 1) goToStep(currentStep + 1);
                else if (diff < 0 && currentStep > 0) goToStep(currentStep - 1);
            }, { passive: true });

            document.getElementById('wf-next-step').addEventListener('click', () => {
                if (!isTransitioning) goToStep(currentStep + 1);
            });
            document.getElementById('wf-prev-step').addEventListener('click', () => {
                if (!isTransitioning) goToStep(currentStep - 1);
            });

            video.addEventListener('loadedmetadata', () => {
                video.currentTime = 0;
                video.pause();
            });
        })();
        </script>
        """,
        unsafe_allow_javascript=True,
    )

    # Order Now button below the video -> redirects to Menu page
    _, cta_col, _ = st.columns([1.4, 1.2, 1.4])
    with cta_col:
        st.write("")
        if st.button("🍔 Order Now", key="home_order_now", type="primary", use_container_width=True):
            st.session_state.page = "Menu"
            st.rerun()

    # 4. Bounded Auto-Scrolling & User-Scrollable Blurred Testimonials Carousel
    st.html(
        """
        <div style="margin-top:3rem;">
            <h2 class="wf-section-title">Voices After <span>Darkness</span></h2>
            <p class="wf-section-sub">Scroll or click any review to pause & explore what our regulars say.</p>
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
                { name: "Junaid", text: "From the first bite to the last crumb, you can taste the craft. 10/10 for both the Tower Burger and Paratha Roll!" }
            ];

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
                        <span>⭐⭐⭐⭐⭐</span>
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

    # 5. Review Section below Testimonials
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
