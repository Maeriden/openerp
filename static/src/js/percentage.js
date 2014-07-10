openerp.ies = function(instance) {

instance.web.form.widgets.add("percentage", "instance.ies.FieldPercentage");
instance.ies.FieldPercentage = instance.web.form.FieldFloat.extend(
{
	template: "FieldPercentage",
	widget_class: "oe_form_field_float oe_form_field_percentage",
	
    init: function (field_manager, node) {
        this._super(field_manager, node);
        this.format_digits = [69, 2];
    },
	
	/**
	*	\param val String with the textual representation of the value.
	*	\param def Default value for the parsed argument.
	*	\ret A number parsed from the string, as a rating (e.g. 40 = 0.4).
	**/
    parse_value: function(val, def)
    {
    	n = instance.web.parse_value(val, {type: "float", digits: (this.node.attrs || {}).digits || this.field.digits}, def);
    	return n / 100.0;
    },
    
	/**
	*	\param val Number to convert to string.
	*	\param def Default value of the argument.
	*	\ret A string, formatted from the number as a percentage (e.g. 0.4 = 40%).
	**/
    format_value: function(val, def)
    {
	//	return instance.web.format_value(val*100.0, {type: "float", digits: (this.node.attrs || {}).digits || this.field.digits}, def);
		return instance.web.format_value(val*100.0, {type: "float", digits: this.format_digits}, def);
    },
});

};
