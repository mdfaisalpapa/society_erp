$(document).ready(function () {
    if (window.location.pathname !== "/login") {
        return;
    }

    var interval = setInterval(function () {
        if (
            window.login &&
            window.login.login_handlers &&
            window.login.login_handlers[200]
        ) {
            clearInterval(interval);

            var original_200 = window.login.login_handlers[200];

            window.login.login_handlers[200] = function (data) {
                if (data.is_desk_user === false) {
                    window.location.replace("/");
                    return;
                }

                original_200(data);
            };
        }
    }, 100);
});
