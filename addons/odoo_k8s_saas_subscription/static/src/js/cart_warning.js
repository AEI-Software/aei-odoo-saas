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
// Uses MutationObserver so it works when Odoo 18 renders the form via interactions/XHR
// (DOMContentLoaded alone fires before the <select id="o_country_id"> exists).
(function () {
    "use strict";
    function _setBolivia(sel) {
        if (!sel || sel.value) return;
        var opt = sel.querySelector('option[code="BO"]');
        if (!opt) return;
        opt.selected = true;
        sel.dispatchEvent(new Event("change", { bubbles: true }));
    }
    function _scan() {
        _setBolivia(document.getElementById("o_country_id"));
    }
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", _scan);
    } else {
        _scan();
    }
    new MutationObserver(_scan).observe(document.body, { childList: true, subtree: true });
})();

// Remove `required` from optional address fields regardless of what Odoo's address.js sets.
// Odoo 18 reads the hidden `required_fields` input and dynamically calls input.required = true.
// We counter that by observing each optional input for `required` attribute changes.
(function () {
    "use strict";
    var OPTIONAL = ["street", "street2", "city", "zip", "state_id"];

    function _clean(el) {
        if (el && el.hasAttribute("required")) {
            el.removeAttribute("required");
        }
    }

    function _attachObservers() {
        OPTIONAL.forEach(function (name) {
            var el = document.querySelector('[name="' + name + '"]');
            if (!el || el._saasOptWatched) return;
            el._saasOptWatched = true;
            _clean(el);
            // Fire every time Odoo re-sets `required` on this element
            new MutationObserver(function () { _clean(el); }).observe(el, {
                attributes: true,
                attributeFilter: ["required"],
            });
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", _attachObservers);
    } else {
        _attachObservers();
    }
    // Re-run when the form re-renders (page change, XHR reload)
    new MutationObserver(_attachObservers).observe(document.body, {
        childList: true,
        subtree: true,
    });
})();
