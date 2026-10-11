frappe.ui.form.on('Resident Vehicle', {
    setup: function(frm) {
        // 1. Filter 'Make' dropdown based on selected 'Vehicle Type' (Car/Bike)
        frm.set_query("make", function() {
            if (frm.doc.vehicle_type) {
                return {
                    filters: {
                        "vehicle_type": frm.doc.vehicle_type
                    }
                };
            }
        });

        // 2. Filter 'Model' dropdown based on selected 'Make'
        frm.set_query("model", function() {
            if (frm.doc.make) {
                return {
                    filters: {
                        "make": frm.doc.make
                    }
                };
            }
        });

        // 3. NEW: Filter 'Parking Slot' based on selected 'Flat'
        frm.set_query("parking_slot", function() {
            if (frm.doc.flat) {
                return {
                    // Filters the dropdown to only show slots belonging to this flat
                    filters: {
                        "owned_by": frm.doc.flat
                    }
                };
            } else {
                frappe.msgprint("Please select a Flat first.");
                return {};
            }
        });
    },

    // Clear dependent fields if the parent field is changed
    vehicle_type: function(frm) {
        frm.set_value('make', '');
        frm.set_value('model', '');
    },
    
    make: function(frm) {
        frm.set_value('model', '');
    },

    // NEW: Clear parking slot if the flat is changed to prevent mismatches
    flat: function(frm) {
        frm.set_value('parking_slot', '');
    }
});
