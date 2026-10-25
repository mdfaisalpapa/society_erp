$(document).ready(function () {
    if (window.location.pathname !== "/login") {
        return;
    }

    var interval = setInterval(function () {
        if (window.login && window.login.login_handlers && window.login.login_handlers[200]) {
            clearInterval(interval);
            
            var original_200 = window.login.login_handlers[200];
            
            // Intercept the successful login response
            window.login.login_handlers[200] = function (data) {
                // Read the custom flag injected by hooks_override.py
                if (data.is_desk_user) {
                    // Let System Users go to /desk naturally
                    original_200(data);
                } else {
                    // Force Website Users (Residents) to the portal
                    window.location.href = "/resident";
                }
            };
        }
    }, 100);
});
