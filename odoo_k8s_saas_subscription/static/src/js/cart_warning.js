/**
 * Cart warning toast — vanilla JS, no Odoo module imports.
 *
 * Intercepts XMLHttpRequest responses to /shop/cart/update_json;
 * if the JSON body contains a "warning" key, display a Bootstrap 5 toast.
 */
(function () {
    "use strict";

    var _origOpen = XMLHttpRequest.prototype.open;
    var _origSend = XMLHttpRequest.prototype.send;

    XMLHttpRequest.prototype.open = function (method, url) {
        this._saasUrl = url;
        return _origOpen.apply(this, arguments);
    };

    XMLHttpRequest.prototype.send = function () {
        var xhr = this;
        if (xhr._saasUrl && xhr._saasUrl.indexOf("/shop/cart/update") !== -1) {
            xhr.addEventListener("load", function () {
                try {
                    var data = JSON.parse(xhr.responseText);
                    if (data && data.warning) {
                        _showToast(data.warning);
                    }
                } catch (e) {
                    // Not JSON or parse error — ignore
                }
            });
        }
        return _origSend.apply(this, arguments);
    };

    var LOGIN_KEYWORD = "iniciar sesión";

    function _showToast(message) {
        var id = "saas-cart-warn-" + Date.now();
        var isLoginWarning = message.indexOf(LOGIN_KEYWORD) !== -1;

        // For login warnings, linkify "iniciar sesión" and "crear una cuenta"
        var body = message;
        if (isLoginWarning) {
            var redirect = encodeURIComponent(window.location.pathname + window.location.search);
            body = message
                .replace(
                    "iniciar sesión",
                    '<a href="/web/login?redirect=' + redirect + '" class="fw-bold text-white">iniciar sesión</a>'
                )
                .replace(
                    "crear una cuenta",
                    '<a href="/web/signup?redirect=' + redirect + '" class="fw-bold text-white">crear una cuenta</a>'
                );
        }

        var colorClass = isLoginWarning ? "text-bg-primary" : "text-bg-warning";
        var icon = isLoginWarning ? "fa-user-circle" : "fa-exclamation-triangle";
        var delay = 30000;

        var html =
            '<div id="' + id + '" ' +
            'class="toast align-items-center ' + colorClass + ' border-0 position-fixed bottom-0 end-0 m-3" ' +
            'role="alert" aria-live="assertive" aria-atomic="true" ' +
            'data-bs-delay="' + delay + '" style="z-index:10000;">' +
            '<div class="d-flex">' +
            '<div class="toast-body fw-semibold">' +
            '<i class="fa ' + icon + ' me-1"></i> ' +
            body +
            '</div>' +
            '<button type="button" class="btn-close btn-close-white me-2 m-auto" ' +
            'data-bs-dismiss="toast" aria-label="Close"></button>' +
            '</div></div>';
        document.body.insertAdjacentHTML("beforeend", html);
        var el = document.getElementById(id);
        if (el && window.bootstrap && window.bootstrap.Toast) {
            var toast = new window.bootstrap.Toast(el);
            toast.show();
            el.addEventListener("hidden.bs.toast", function () { el.remove(); });
        }
    }
})();

// Pre-select Bolivia on the address form if no country is chosen yet.
(function () {
    "use strict";
    function _setBoliviaDefault() {
        var sel = document.getElementById("o_country_id");
        if (!sel) return;
        if (sel.value) return; // already has a value
        var opt = sel.querySelector('option[code="BO"]');
        if (opt) {
            opt.selected = true;
            // Trigger change so Odoo updates state/zip visibility
            sel.dispatchEvent(new Event("change", { bubbles: true }));
        }
    }
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", _setBoliviaDefault);
    } else {
        _setBoliviaDefault();
    }
})();
