/* globals _ */

(function () {
    'use strict';

    var ChangeDue = (function () {
        function ChangeDueInner($section) {
            this.$section = $section;
            this.$section.data('wrapper', this);

            this.$cohort = this.$section.find(".change-due-cohort");
            this.$user = this.$section.find(".change-due-user");
            this.$block_location = this.$section.find("#change-due-location");
            this.$set_date = this.$section.find(".change-due-set");
            this.$add_days = this.$section.find(".change-due-add");
            this.init();
            this.$submit_button = this.$section.find("#change-due-button");
            this.$radios = this.$section.find(".list-fields input[type=radio]");
            this.$show_button = this.$section.find("#change-due-tasks").find("input");
            var self = this;
            this.$submit_button.click(
                function(event){
                    self.onSubmitForm(event);
                }
            );
            this.$radios.click(
                function(event){
                    self.changeDueExclude(event);
                }
            );
            this.$show_button.click(
                function (event) {
                    self.showTasksStatus(event);
                }
            );
            console.log("Build change due");
        }

        ChangeDueInner.prototype.init = function () {
            this.$section.find(".change-due-when input[value=add]").prop("checked", true);
            this.$section.find(".change-due-who input[value=user]").prop("checked", true);
            this.$section.find(".change-due-where input[value=block]").prop("checked", true);
            this.$cohort.addClass("hidden");
            this.$set_date.addClass("hidden");
            var form = this.$section.find("#change-due-tasks");
            var table = form.find("table");
            table.addClass("hidden");
        };

        ChangeDueInner.prototype.onClickTitle = function () {
            this.init();
        };

        ChangeDueInner.prototype.onSubmitForm = function (arg) {
            var form = this.$section.find("#form-change-due");
            var dataurl = form.attr('action');
            var msg = form.serialize();
            var self = this;
            $.ajax({
                type: 'POST',
                url: dataurl,
                data: msg,
                dataType: "json",
                success: function () {
                    self.$section.find('.request-response-message').removeClass("hidden");
                    self.$section.find('#section-change-due').find('.request-response-error').html("");
                },
                error: function (data) {
                    self.$section.find('#section-change-due').find('.request-response-error').html(data["responseJSON"]['message']);
                    self.$section.find('.request-response-message').addClass("hidden");
                }
            });
        };

        ChangeDueInner.prototype.changeDueExclude = function (event) {
            var set_state = event.target.value;
            var $radio_set = this.$section.find("input[type=radio][name=when][value=set]");
            var $radio_course = this.$section.find("input[type=radio][name=where][value=course]");

            if ( set_state == "user") {
                this.$cohort.addClass("hidden");
                this.$user.removeClass("hidden");
            }
            if (set_state == "cohort") {
                this.$cohort.removeClass("hidden");
                this.$user.addClass("hidden");
            }
            if (set_state == "course") {
                this.$block_location.addClass("is-disabled");
                this.$block_location.find('input').addClass("blocked");
                $radio_set.attr("disabled" ,true);
            }
            if (set_state  == "block") {
                this.$block_location.removeClass("is-disabled");
                this.$block_location.find('input').removeClass("blocked");
                $radio_set.attr("disabled", false );
            }
            if (set_state == "add") {
                this.$set_date.addClass("hidden");
                this.$add_days.removeClass("hidden");
                $radio_course.attr("disabled", false);
            }
            if (set_state == "set") {
                this.$set_date.removeClass("hidden");
                this.$add_days.addClass("hidden");
                $radio_course.attr("disabled", true);
            }
        };

        ChangeDueInner.prototype.getTableRow = function(obj){
            var resstr = "<tr>";
            var args = [obj.id, obj.author, obj.status, obj.date, obj.who, obj.where, obj.when];
            for (var i=0; i<args.length; i++) {
                resstr += "<td>"+ args[i] + "</td>";
            }
            return resstr;
        };

        ChangeDueInner.prototype.showTasksStatus = function (event) {
            var form = this.$section.find("#change-due-tasks");
            form.find('table').removeClass("hidden");
            var tbody = form.find("tbody");
            var url = this.$show_button.attr("data-endpoint");
            var self = this;
            tbody.html('');
            $.ajax({
                type: 'GET',
                url: url,
                dataType: "json",
                success: function (data) {
                    var tasks = data["tasks"];
                    for (var i=0; i<tasks.length; i++){
                        tbody.append(self.getTableRow(tasks[i]));
                    }
                }
            });
        };

        return ChangeDueInner;
    }());

    _.defaults(window, {
        InstructorDashboard: {}
    });

    _.defaults(window.InstructorDashboard, {
        sections: {}
    });

    _.defaults(window.InstructorDashboard.sections, {
        ChangeDue: ChangeDue
    });

    this.ChangeDue = ChangeDue;
}).call(this);
