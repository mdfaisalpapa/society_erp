$(document).ready(function() {
    let style = document.createElement('style');
    style.innerHTML = `
        /* Target the exact data-action attribute used in Frappe v15/v16 MultiSelect */
        button[data-action="select_all"], 
        .frappe-control[data-fieldtype="MultiSelect"] .btn-group button:first-child { 
            display: none !important; 
            visibility: hidden !important;
        }
        
        /* Expand the Clear button to look normal */
        button[data-action="clear_all"] {
            width: 100% !important;
            border-radius: 4px !important;
        }
    `;
    document.head.appendChild(style);
});
