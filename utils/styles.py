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
    --wf-border: rgba(212, 175, 55, 0.24);
}

/* Hide Streamlit default chrome for a clean website feel */
#MainMenu, header[data-testid="stHeader"], footer, [data-testid="stToolbar"] {
    visibility: hidden !important;
    height: 0 !important;
}

.stApp, [data-testid="stAppViewContainer"] {
    background-color: var(--wf-bg) !important;
    color: var(--wf-cream) !important;
    font-family: 'Plus Jakarta Sans', sans-serif !important;
}

.block-container {
    padding-top: 1.1rem !important;
    padding-bottom: 3rem !important;
    max-width: 1220px !important;
}

/* Blur-in reveal animation triggered after intro video fades out */
@keyframes wfBlurReveal {
    0% {
        opacity: 0;
        filter: blur(20px);
        transform: scale(1.015);
    }
    100% {
        opacity: 1;
        filter: blur(0px);
        transform: scale(1);
    }
}

.wf-blur-in {
    animation: wfBlurReveal 1.25s cubic-bezier(0.22, 1, 0.36, 1) forwards;
}

/* Brand & Toolbar */
.wf-brand-wrap {
    display: flex;
    align-items: center;
    gap: 12px;
}

.wf-brand-logo {
    height: 46px;
    width: auto;
    object-fit: contain;
    border-radius: 10px;
}

.wf-brand-name {
    font-family: 'Lobster', cursive !important;
    font-size: 2rem !important;
    color: var(--wf-gold) !important;
    letter-spacing: 0.5px;
    line-height: 1.1;
    text-shadow: 0 2px 14px rgba(212, 175, 55, 0.25);
    white-space: nowrap;
}

/* Buttons styled in Charcoal Black & Warm Gold */
div.stButton > button,
div[data-testid="stPopover"] > button {
    background: linear-gradient(135deg, #1E1C18, #161512) !important;
    color: var(--wf-cream) !important;
    border: 1px solid var(--wf-border) !important;
    border-radius: 999px !important;
    padding: 0.5rem 1.2rem !important;
    font-family: 'Plus Jakarta Sans', sans-serif !important;
    font-weight: 600 !important;
    transition: all 0.25s ease !important;
}

div.stButton > button:hover,
div[data-testid="stPopover"] > button:hover {
    border-color: var(--wf-gold) !important;
    color: var(--wf-gold-bright) !important;
    box-shadow: 0 0 18px rgba(212, 175, 55, 0.22) !important;
    transform: translateY(-1px);
}

/* Primary Warm Gold CTA Buttons */
div.stButton > button[kind="primary"],
div.stFormSubmitButton > button {
    background: linear-gradient(135deg, #D4AF37, #B88E24) !important;
    color: #121212 !important;
    border: none !important;
    border-radius: 999px !important;
    font-weight: 700 !important;
    letter-spacing: 0.3px;
    box-shadow: 0 6px 20px rgba(212, 175, 55, 0.28) !important;
}

div.stButton > button[kind="primary"]:hover,
div.stFormSubmitButton > button:hover {
    background: linear-gradient(135deg, #ECC95B, #D4AF37) !important;
    color: #0D0D0D !important;
    box-shadow: 0 8px 26px rgba(212, 175, 55, 0.42) !important;
}

/* Divider */
.wf-nav-divider {
    height: 1px;
    background: linear-gradient(90deg, transparent, rgba(212, 175, 55, 0.45), transparent);
    margin: 0.65rem 0 1.4rem 0;
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
    transition: transform 0.3s ease, border-color 0.3s ease;
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
    margin: 0.6rem 0 0.25rem 0;
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
    margin-bottom: 0.6rem;
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
    background: radial-gradient(circle at 50% 35%, rgba(212, 175, 55, 0.22), #101010 75%);
    border: 1px dashed rgba(212, 175, 55, 0.3);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 4.5rem;
}

/* Inputs & Modals */
textarea, input[type="text"] {
    background-color: #191815 !important;
    color: var(--wf-cream) !important;
    border: 1px solid rgba(212, 175, 55, 0.28) !important;
    border-radius: 12px !important;
}

textarea:focus, input[type="text"]:focus {
    border-color: var(--wf-gold) !important;
    box-shadow: 0 0 0 1px var(--wf-gold) !important;
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
