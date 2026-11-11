/** @odoo-module **/
/**
 * QR Banco Ganadero — frontend polling + demo simulation.
 * Uses safe DOM APIs (replaceChildren, createElement, textContent) with zero innerHTML.
 */

import { browser } from "@web/core/browser/browser";

const POLL_INTERVAL_MS = 3000;
const MAX_ATTEMPTS = 200;

function renderStatusBanner(container, cssClass, messageText) {
    if (!container) {
        return;
    }
    container.replaceChildren();
    const span = document.createElement("span");
    span.className = cssClass;
    span.textContent = messageText;
    container.appendChild(span);
}

function startQrGanaderoPolling() {
    const refInput = document.getElementById("qr_ganadero_reference");
    const statusUrlInput = document.getElementById("qr_ganadero_status_url");
    const landingInput = document.getElementById("qr_ganadero_landing");
    const msgEl = document.getElementById("qr_ganadero_status_msg");

    if (!refInput || !statusUrlInput) {
        return;
    }

    const reference = refInput.value;
    const statusUrl = statusUrlInput.value;
    const landingRoute = (landingInput && landingInput.value) || "/payment/status";
    if (!reference || !statusUrl) {
        return;
    }

    let attempts = 0;
    const intervalId = setInterval(async () => {
        attempts += 1;
        if (attempts > MAX_ATTEMPTS) {
            clearInterval(intervalId);
            renderStatusBanner(
                msgEl,
                "text-warning",
                "Tiempo de espera agotado. Si ya realizaste el pago, tu orden se confirmará automáticamente."
            );
            return;
        }

        try {
            const resp = await fetch(statusUrl, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ jsonrpc: "2.0", method: "call", params: { reference } }),
            });
            const data = await resp.json();
            const result = data.result || {};
            const state = result.state;

            if (result.is_demo) {
                clearInterval(intervalId);
                renderStatusBanner(
                    msgEl,
                    "text-info fw-semibold",
                    "Modo Demo activo: presiona el botón Simular Pago (Demo) para confirmar la orden."
                );
                return;
            }

            if (state === "done") {
                clearInterval(intervalId);
                renderStatusBanner(msgEl, "text-success fw-bold", "Pago confirmado. Redirigiendo...");
                browser.setTimeout(() => {
                    window.location.href = landingRoute;
                }, 1500);
            } else if (state === "cancel" || state === "error") {
                clearInterval(intervalId);
                renderStatusBanner(msgEl, "text-danger", "El pago fue cancelado o rechazado.");
            }
        } catch (_err) {
            // Keep polling silently on transient network glitches
        }
    }, POLL_INTERVAL_MS);

    const simulateBtn = document.getElementById("qr_ganadero_simulate_btn");
    const simulateUrlInput = document.getElementById("qr_ganadero_simulate_url");

    if (simulateBtn && simulateUrlInput) {
        const simulateUrl = simulateUrlInput.value;
        let isSimulating = false;

        simulateBtn.addEventListener("click", async () => {
            if (isSimulating) {
                return;
            }
            isSimulating = true;
            simulateBtn.disabled = true;
            simulateBtn.textContent = "Procesando...";

            try {
                const resp = await fetch(simulateUrl, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        jsonrpc: "2.0",
                        method: "call",
                        params: { reference },
                    }),
                });
                const data = await resp.json();
                const result = data.result || {};

                if (result.status === "ok" || result.status === "already_done") {
                    clearInterval(intervalId);
                    renderStatusBanner(
                        msgEl,
                        "text-success fw-bold",
                        "Pago simulado correctamente. Redirigiendo..."
                    );
                    browser.setTimeout(() => {
                        window.location.href = result.landing_route || landingRoute;
                    }, 1200);
                } else {
                    isSimulating = false;
                    simulateBtn.disabled = false;
                    simulateBtn.textContent = "Simular Pago (Demo)";
                    renderStatusBanner(
                        msgEl,
                        "text-danger",
                        "Error al simular pago: " + (result.message || "error desconocido")
                    );
                }
            } catch (_err) {
                isSimulating = false;
                simulateBtn.disabled = false;
                simulateBtn.textContent = "Simular Pago (Demo)";
                renderStatusBanner(msgEl, "text-danger", "Error de red al simular el pago.");
            }
        });
    }
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", startQrGanaderoPolling);
} else {
    startQrGanaderoPolling();
}

