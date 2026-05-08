---
name: Liquid Glass Aesthetic
colors:
  surface: '#10131a'
  surface-dim: '#10131a'
  surface-bright: '#363941'
  surface-container-lowest: '#0b0e15'
  surface-container-low: '#191b23'
  surface-container: '#1d2027'
  surface-container-high: '#272a31'
  surface-container-highest: '#32353c'
  on-surface: '#e1e2ec'
  on-surface-variant: '#c2c6d6'
  inverse-surface: '#e1e2ec'
  inverse-on-surface: '#2e3038'
  outline: '#8c909f'
  outline-variant: '#424754'
  surface-tint: '#adc6ff'
  primary: '#adc6ff'
  on-primary: '#002e6a'
  primary-container: '#4d8eff'
  on-primary-container: '#00285d'
  inverse-primary: '#005ac2'
  secondary: '#4cd7f6'
  on-secondary: '#003640'
  secondary-container: '#03b5d3'
  on-secondary-container: '#00424e'
  tertiary: '#ffb786'
  on-tertiary: '#502400'
  tertiary-container: '#df7412'
  on-tertiary-container: '#461f00'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#d8e2ff'
  primary-fixed-dim: '#adc6ff'
  on-primary-fixed: '#001a42'
  on-primary-fixed-variant: '#004395'
  secondary-fixed: '#acedff'
  secondary-fixed-dim: '#4cd7f6'
  on-secondary-fixed: '#001f26'
  on-secondary-fixed-variant: '#004e5c'
  tertiary-fixed: '#ffdcc6'
  tertiary-fixed-dim: '#ffb786'
  on-tertiary-fixed: '#311400'
  on-tertiary-fixed-variant: '#723600'
  background: '#10131a'
  on-background: '#e1e2ec'
  surface-variant: '#32353c'
typography:
  display:
    fontFamily: Inter
    fontSize: 48px
    fontWeight: '300'
    lineHeight: '1.1'
    letterSpacing: -0.02em
  h1:
    fontFamily: Inter
    fontSize: 32px
    fontWeight: '400'
    lineHeight: '1.2'
    letterSpacing: -0.01em
  h2:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '400'
    lineHeight: '1.3'
    letterSpacing: 0.01em
  body-lg:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '400'
    lineHeight: '1.6'
    letterSpacing: 0.02em
  body-md:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: '1.6'
    letterSpacing: 0.02em
  label-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '600'
    lineHeight: '1.0'
    letterSpacing: 0.1em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  unit: 4px
  xs: 8px
  sm: 16px
  md: 24px
  lg: 48px
  xl: 80px
  container-max: 1440px
  gutter: 24px
---

## Brand & Style

The design system is centered on the concept of "liquid glass"—a high-fidelity, ethereal aesthetic that prioritizes depth through optical refraction rather than solid mass. It is designed for high-end tech platforms, creative suites, or premium data environments where focus and clarity are paramount. 

The brand personality is sophisticated, calm, and technologically advanced. It avoids the "heavy" feel of traditional dark modes by utilizing multi-layered background blurs and micro-interactions that feel fluid and organic. The goal is to create a UI that feels less like a series of containers and more like a singular, cohesive atmosphere where information floats in a deep, obsidian space.

## Colors

This design system utilizes a hyper-dark foundation to maximize the luminosity of glass effects and accents. 

- **The Base:** Deepest charcoal (#050505) acts as the "void" layer, providing infinite depth.
- **The Glass:** Surfaces are near-transparent white tints (3-5% opacity), relying on backdrop blurs (20px to 40px) to create separation.
- **Accents:** Vibrant Blue (#3b82f6) and Cyan are used exclusively for functional signaling—active states, progress indicators, and primary actions. 
- **Gradients:** Use subtle, large-scale radial gradients in the background (15% opacity Blue/Cyan) to simulate distant light sources reflecting through the glass layers.

## Typography

The typography strategy leverages **Inter** for its neutral, systematic clarity. To achieve the "premium" feel, the system employs wide letter-spacing (tracking) on body and label text, creating an airy, breathable reading experience.

Headlines should remain thin or regular in weight to maintain the minimalist ethos. Use "Display" sizes for hero moments, utilizing negative letter-spacing for a tight, editorial look. For all interactive labels, use uppercase with generous tracking (0.1em) to distinguish them from content without requiring heavy boxes or backgrounds.

## Layout & Spacing

The layout is governed by a **Fluid Grid** model with generous margins to reinforce the sense of "ethereal" space. Elements should never feel cramped; the design system favors whitespace over dividers.

- **Margins:** Standard page margins should be at least `lg` (48px) to allow the "void" background to frame the content.
- **Negative Space:** Use vertical spacing to group elements instead of lines. 
- **Alignment:** Content is strictly aligned to a 12-column grid, but components (like glass panels) may bleed across gutters to create a seamless, liquid flow.

## Elevation & Depth

Depth is the primary navigator in this system. It is achieved through three layers:

1.  **The Void (Level 0):** The #050505 background.
2.  **The Liquid Layer (Level 1):** Elements floating just above the void. High transparency (3%), backdrop-filter: blur(20px), and a 0.5px border (White @ 8% opacity).
3.  **The Focus Layer (Level 2):** Modals or active panels. Increased backdrop blur (40px) and a subtle outer glow (0px 0px 20px Blue @ 10% opacity) instead of a shadow.

Avoid hard shadows. If a shadow is necessary, it must be an "Ambient Glow"—a highly diffused (60px+ blur) color-tinted shadow that mimics light passing through tinted glass.

## Shapes

The design system uses a consistent **Rounded** (0.5rem base) language to evoke the feel of polished, tumbled glass. 

- **Small elements (Inputs, Buttons):** 8px (0.5rem).
- **Large containers (Glass Panels):** 16px (1rem).
- **Interactive zones:** Maintain smooth, continuous curves (Squircle-like) where possible to avoid the mechanical feel of hard geometric corners.

## Components

### Buttons
Primary buttons use a semi-transparent vibrant blue (#3b82f6) with a heavy backdrop blur. Text is white. Secondary buttons are "Ghost Glass"—no fill, just a 1px soft border and a blur effect that intensifies on hover.

### Glass Panels (Cards)
Replace traditional cards with "Liquid Panels." These have no solid background. They use `backdrop-filter: blur(30px)` and a top-to-bottom subtle gradient stroke to simulate a light catch on the "top" edge of the glass.

### Input Fields
Inputs are simple 0.5px bottom-borders or fully encapsulated glass shapes with 2% white opacity. On focus, the border transitions to a cyan glow, and the background blur slightly increases.

### Chips & Tags
Pill-shaped with a 10% opacity tint of the accent color. No borders. Text weight should be slightly higher (Medium 500) to ensure legibility against the blurred background.

### Navigation
The navigation bar should be a "Floating Frost" element—a detached glass bar with a high blur factor, floating at the top of the viewport with a subtle outer glow to separate it from the content scrolling beneath.