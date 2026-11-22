GLOBAL_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Lobster&family=Playfair+Display:ital,wght@0,500;0,700;0,900;1,600&family=Plus+Jakarta+Sans:wght@300;400;500;600;700&display=swap');

:root {
    --wf-bg: #121212;
    --wf-surface: #1A1917;
    --wf-surface-2: #22201C;
    --wf-cream: #F5EFE6;
    --wf-cream-muted: #CFC4B4;
    --wf-gold: #D4AF37;
    --wf-gold-bright: #F0CA5A;
    --wf-border: rgba(212, 175, 55, 0.26);
}

/* Hide Streamlit chrome */
#MainMenu, header[data-testid="stHeader"], footer, [data-testid="stToolbar"] {
    visibility: hidden !important;
    height: 0 !important;
}

html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"] {
    background-color: var(--wf-bg) !important;
    color: var(--wf-cream) !important;
    font-family: 'Plus Jakarta Sans', sans-serif !important;
    overflow-x: hidden !important;
    overscroll-behavior-y: none !important;
}

.block-container {
    padding-top: 0.9rem !important;
    padding-bottom: 3.5rem !important;
    max-width: 1240px !important;
}

/* Fade-In-Blur-In Reveal */
@keyframes wfBlurReveal {
    0% {
        opacity: 0;
        filter: blur(22px);
        transform: scale(1.015);
    }
    99% {
        opacity: 1;
        filter: blur(0px);
        transform: scale(1);
    }
    100% {
        opacity: 1;
        filter: none;
        transform: none;
    }
}

.wf-page-hidden {
    opacity: 0 !important;
    filter: blur(22px) !important;
}

.wf-blur-in {
    animation: wfBlurReveal 1.2s cubic-bezier(0.22, 1, 0.36, 1) forwards;
}

/* Upper-Left Brand & Larger Logo (Never overlaps adjacent buttons) */
.wf-brand-wrap {
    display: flex;
    align-items: center;
    gap: 14px;
    min-width: 0;
}

.wf-brand-logo {
    height: clamp(56px, 6.2vw, 82px);
    width: auto;
    flex-shrink: 0;
    object-fit: contain;
    border-radius: 14px;
    filter: drop-shadow(0 6px 18px rgba(0, 0, 0, 0.6));
}

.wf-brand-name {
    font-family: 'Lobster', cursive !important;
    font-size: clamp(1.5rem, 2.3vw, 2.25rem) !important;
    color: var(--wf-gold) !important;
    letter-spacing: 0.5px;
    line-height: 1.05;
    text-shadow: 0 2px 16px rgba(212, 175, 55, 0.28);
    white-space: nowrap;
}

/* Responsive Navbar Row so Home never overlaps Brand on desktop or mobile */
.st-key-navbar_wrap [data-testid="stHorizontalBlock"] {
    align-items: center !important;
    gap: 0.65rem !important;
}

@media (max-width: 820px) {
    .st-key-navbar_wrap [data-testid="stHorizontalBlock"] {
        display: flex !important;
        flex-direction: row !important;
        flex-wrap: wrap !important;
        align-items: center !important;
        gap: 0.5rem !important;
    }
    .st-key-navbar_wrap [data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-child(1) {
        flex: 1 1 calc(100% - 72px) !important;
        width: auto !important;
        min-width: 0 !important;
        order: 1 !important;
    }
    .st-key-navbar_wrap [data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-child(6) {
        flex: 0 0 56px !important;
        width: 56px !important;
        min-width: 56px !important;
        order: 2 !important;
    }
    .st-key-navbar_wrap [data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-child(2),
    .st-key-navbar_wrap [data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-child(3),
    .st-key-navbar_wrap [data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-child(4),
    .st-key-navbar_wrap [data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-child(5) {
        flex: 1 1 auto !important;
        width: auto !important;
        min-width: max-content !important;
        order: 3 !important;
    }
    .st-key-navbar_wrap div.stButton > button {
        padding: 0.42rem 0.8rem !important;
        font-size: 0.85rem !important;
    }
}

/* Standard Navigation & Action Buttons */
div.stButton > button {
    background: linear-gradient(135deg, #1E1C18, #161512) !important;
    color: var(--wf-cream) !important;
    border: 1px solid var(--wf-border) !important;
    border-radius: 999px !important;
    padding: 0.5rem 1.05rem !important;
    font-family: 'Plus Jakarta Sans', sans-serif !important;
    font-weight: 600 !important;
    white-space: nowrap !important;
    transition: all 0.28s cubic-bezier(0.22, 1, 0.36, 1) !important;
}

div.stButton > button:hover {
    border-color: var(--wf-gold) !important;
    color: var(--wf-gold-bright) !important;
    box-shadow: 0 0 18px rgba(212, 175, 55, 0.24) !important;
    transform: translateY(-1px);
}

/* Primary Warm Gold Buttons */
div.stButton > button[kind="primary"],
div.stFormSubmitButton > button,
.st-key-basket_order_btn button {
    background: linear-gradient(135deg, #D4AF37, #B88E24) !important;
    color: #121212 !important;
    border: none !important;
    border-radius: 999px !important;
    font-weight: 700 !important;
    letter-spacing: 0.3px;
    box-shadow: 0 6px 20px rgba(212, 175, 55, 0.28) !important;
}

div.stButton > button[kind="primary"]:hover,
div.stFormSubmitButton > button:hover,
.st-key-basket_order_btn button:hover {
    background: linear-gradient(135deg, #ECC95B, #D4AF37) !important;
    color: #0D0D0D !important;
    box-shadow: 0 8px 26px rgba(212, 175, 55, 0.42) !important;
}

/* Top-Right Bag Icon + Overlapping Item Count Badge */
.st-key-bag_popover {
    display: flex !important;
    justify-content: flex-end !important;
}

.st-key-bag_popover button {
    position: relative !important;
    width: 50px !important;
    height: 50px !important;
    min-height: 50px !important;
    padding: 0 !important;
    border-radius: 15px !important;
    background: linear-gradient(135deg, #211F1A, #151411) !important;
    border: 1px solid rgba(212, 175, 55, 0.48) !important;
    overflow: visible !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    transition: all 0.28s cubic-bezier(0.22, 1, 0.36, 1) !important;
}

.st-key-bag_popover button:hover {
    border-color: #F0CA5A !important;
    box-shadow: 0 0 20px rgba(212, 175, 55, 0.28) !important;
    transform: translateY(-2px) scale(1.03);
}

.st-key-bag_popover button::before {
    content: "";
    width: 24px;
    height: 24px;
    display: block;
    background-repeat: no-repeat;
    background-position: center;
    background-size: contain;
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23F5EFE6' stroke-width='1.9' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M6 7h12l1 13H5L6 7z'/%3E%3Cpath d='M9 7V5a3 3 0 0 1 6 0v2'/%3E%3C/svg%3E");
}

.st-key-bag_popover button svg {
    display: none !important;
}

.st-key-bag_popover button [data-testid="stMarkdownContainer"],
.st-key-bag_popover button p {
    position: absolute !important;
    top: -7px !important;
    right: -7px !important;
    margin: 0 !important;
    padding: 0 5px !important;
    min-width: 22px !important;
    height: 22px !important;
    line-height: 20px !important;
    border-radius: 999px !important;
    background: #D4AF37 !important;
    color: #121212 !important;
    font-size: 0.76rem !important;
    font-weight: 800 !important;
    text-align: center !important;
    border: 2px solid #121212 !important;
    box-shadow: 0 3px 10px rgba(0, 0, 0, 0.7) !important;
    pointer-events: none !important;
}

/* Buttery Pop-Out Animation for Basket Popover & '+'/'-' Fixes */
@keyframes wfBagPopOut {
    0% {
        opacity: 0;
        transform: scale(0.68) translate(16px, -18px);
        filter: blur(8px);
    }
    70% {
        opacity: 1;
        transform: scale(1.02) translate(0, 2px);
        filter: blur(0px);
    }
    100% {
        opacity: 1;
        transform: scale(1) translate(0, 0);
        filter: blur(0px);
    }
}

div[data-testid="stPopoverBody"] {
    min-width: min(350px, 90vw) !important;
    background: linear-gradient(160deg, #1E1C18, #141311) !important;
    border: 1px solid rgba(212, 175, 55, 0.42) !important;
    border-radius: 18px !important;
    color: var(--wf-cream) !important;
    box-shadow: 0 22px 55px rgba(0, 0, 0, 0.78) !important;
    transform-origin: top right !important;
    animation: wfBagPopOut 0.36s cubic-bezier(0.22, 1, 0.36, 1) forwards !important;
}

div[data-testid="stPopoverBody"] div.stButton > button {
    padding: 0.25rem 0.5rem !important;
    min-width: 34px !important;
    min-height: 34px !important;
    border-radius: 10px !important;
    font-size: 1.05rem !important;
    font-weight: 700 !important;
    line-height: 1 !important;
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
}

div[data-testid="stPopoverBody"] .st-key-basket_order_btn button {
    padding: 0.6rem 1.2rem !important;
    min-height: 42px !important;
    border-radius: 999px !important;
    font-size: 0.98rem !important;
}

/* Buttery Fade-In-Upwards Animation for Checkout / Confirmation Dialogs */
@keyframes wfDialogFadeUp {
    0% {
        opacity: 0;
        transform: translateY(42px) scale(0.97);
        filter: blur(10px);
    }
    100% {
        opacity: 1;
        transform: translateY(0) scale(1);
        filter: blur(0px);
    }
}

div[role="dialog"] {
    background: linear-gradient(165deg, #1C1A16 0%, #12110F 100%) !important;
    border: 1px solid rgba(212, 175, 55, 0.42) !important;
    border-radius: 22px !important;
    box-shadow: 0 30px 90px rgba(0, 0, 0, 0.88) !important;
    animation: wfDialogFadeUp 0.48s cubic-bezier(0.22, 1, 0.36, 1) forwards !important;
}

/* Divider */
.wf-nav-divider {
    height: 1px;
    background: linear-gradient(90deg, transparent, rgba(212, 175, 55, 0.45), transparent);
    margin: 0.55rem 0 1.2rem 0;
}

/* Section Headers */
.wf-section-title {
    font-family: 'Playfair Display', serif;
    font-size: clamp(1.8rem, 3.2vw, 2.6rem);
    color: var(--wf-cream);
    text-align: center;
    margin-bottom: 0.35rem;
}

.wf-section-title span {
    color: var(--wf-gold);
    font-family: 'Lobster', cursive;
    font-weight: 400;
}

.wf-section-sub {
    text-align: center;
    color: var(--wf-cream-muted);
    font-size: 0.98rem;
    margin-bottom: 1.6rem;
}

/* Menu Cards */
.wf-menu-card {
    background: linear-gradient(160deg, #1D1B17 0%, #141311 100%);
    border: 1px solid var(--wf-border);
    border-radius: 22px;
    padding: 1.4rem;
    margin-bottom: 1rem;
    box-shadow: 0 18px 40px rgba(0, 0, 0, 0.45);
    transition: transform 0.32s cubic-bezier(0.22, 1, 0.36, 1), border-color 0.3s ease;
}

.wf-menu-card:hover {
    transform: translateY(-4px);
    border-color: var(--wf-gold);
}

.wf-menu-title {
    font-family: 'Playfair Display', serif;
    font-size: 1.65rem;
    font-weight: 700;
    color: var(--wf-cream);
    margin: 0.7rem 0 0.3rem 0;
}

.wf-menu-price {
    display: inline-block;
    background: rgba(212, 175, 55, 0.14);
    border: 1px solid rgba(212, 175, 55, 0.45);
    color: var(--wf-gold-bright);
    font-weight: 700;
    font-size: 1.05rem;
    padding: 0.25rem 0.85rem;
    border-radius: 999px;
    margin-bottom: 0.65rem;
}

.wf-menu-desc {
    color: var(--wf-cream-muted);
    font-size: 0.94rem;
    line-height: 1.55;
    min-height: 3.1rem;
}

.wf-menu-placeholder {
    height: 220px;
    border-radius: 14px;
    background: radial-gradient(circle at 50% 35%, rgba(212, 175, 55, 0.16), #101010 75%);
    border: 1px dashed rgba(212, 175, 55, 0.35);
    display: flex;
    align-items: center;
    justify-content: center;
    font-family: 'Lobster', cursive;
    font-size: 2rem;
    color: var(--wf-gold);
    letter-spacing: 1px;
}

/* Inputs, TextAreas & Alerts */
textarea, input[type="text"] {
    background-color: #191815 !important;
    color: var(--wf-cream) !important;
    border: 1px solid rgba(212, 175, 55, 0.28) !important;
    border-radius: 12px !important;
    transition: border-color 0.25s ease, box-shadow 0.25s ease !important;
}

textarea:focus, input[type="text"]:focus {
    border-color: var(--wf-gold) !important;
    box-shadow: 0 0 0 1px var(--wf-gold) !important;
}

div[data-testid="stAlert"] {
    border-radius: 14px !important;
    border: 1px solid rgba(212, 175, 55, 0.45) !important;
}

.wf-jazzcash-box {
    background: linear-gradient(135deg, rgba(212, 175, 55, 0.14), rgba(20, 19, 17, 0.95));
    border: 1px solid var(--wf-gold);
    border-radius: 14px;
    padding: 1rem 1.1rem;
    margin: 0.6rem 0 0.9rem 0;
    color: var(--wf-cream);
}

.wf-order-id-box {
    background: #181714;
    border: 1px dashed var(--wf-gold);
    border-radius: 16px;
    padding: 1.2rem;
    text-align: center;
    margin: 0.8rem 0;
}

.wf-order-id-code {
    font-family: 'Playfair Display', serif;
    font-size: 2.2rem;
    font-weight: 800;
    letter-spacing: 3px;
    color: var(--wf-gold-bright);
}
</style>
"""
