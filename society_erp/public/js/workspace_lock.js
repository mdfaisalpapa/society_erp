$(document).ready(function() {
    let style = document.createElement('style');
    style.innerHTML = `
        /* 1. Hide the Select All button in report filter dropdowns */
        .dropdown-menu .btn-group button:first-child,
        button[data-action="selectAll"] { 
            display: none !important; 
        }
        
        /* 2. Expand the Clear All button to fill the space cleanly */
        .dropdown-menu .btn-group button:last-child {
            width: 100% !important;
            border-radius: 4px !important;
        }
    `;
    document.head.appendChild(style);
});