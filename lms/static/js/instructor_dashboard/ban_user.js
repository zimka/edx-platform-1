/* globals _, AutoEnrollmentViaCsv, NotificationModel, NotificationView */

/*
BanUser Section

imports from other modules.
wrap in (-> ... apply) to defer evaluation
such that the value can be defined later than this assignment (file load order).
*/


(function() {
    'use strict';
    var BanOnCourse, BanUser, emailStudents, plantTimeout, statusAjaxError,
        /* eslint-disable */
        __hasProp = {}.hasOwnProperty,
        __extends = function(child, parent) { for (var key in parent) { if (__hasProp.call(parent, key)) child[key] = parent[key]; } function ctor() { this.constructor = child; } ctor.prototype = parent.prototype; child.prototype = new ctor(); child.__super__ = parent.prototype; return child; };
        /* eslint-enable */

    plantTimeout = function() {
        return window.InstructorDashboard.util.plantTimeout.apply(this, arguments);
    };

    statusAjaxError = function() {
        return window.InstructorDashboard.util.statusAjaxError.apply(this, arguments);
    };

    emailStudents = false;

    BanOnCourse = (function() {
        function banOnCourse($container) {
            var batchEnroll = this;
            this.$container = $container;
            this.$identifier_input = this.$container.find("textarea[name='student-ids']");
            this.$ban_button = this.$container.find('.ban-button');
            this.$task_response = this.$container.find('.request-response');
            this.$request_response_error = this.$container.find('.request-response-error');
            this.$ban_button.click(function(event) {
                var sendData;
                sendData = {
                    action: $(event.target).data('action'),
                    identifiers: batchEnroll.$identifier_input.val()
                };
                return $.ajax({
                    dataType: 'json',
                    type: 'POST',
                    url: $(event.target).data('endpoint'),
                    data: sendData,
                    success: function(data) {
                        return batchEnroll.display_response(data);
                    },
                    error: statusAjaxError(function() {
                        return batchEnroll.fail_with_error(gettext('Error while ban user.'));
                    })
                });
            });
        }

        banOnCourse.prototype.clear_input = function() {
            this.$identifier_input.val('');
        };

        banOnCourse.prototype.fail_with_error = function(msg) {
            this.clear_input();
            this.$task_response.empty();
            this.$request_response_error.empty();
            return this.$request_response_error.text(msg);
        };

        banOnCourse.prototype.display_response = function(dataFromServer) {
            var allowed, autoenrolled, enrolled, errors, errorsLabel,
                invalidIdentifier, notenrolled, notunenrolled, renderList, sr, studentResults,
                i, j, len, len1, ref, renderIdsLists,
                displayResponse = this;
            this.clear_input();
            this.$task_response.empty();
            this.$request_response_error.empty();
            invalidIdentifier = [];
            errors = [];
            enrolled = [];
            allowed = [];
            autoenrolled = [];
            notenrolled = [];
            notunenrolled = [];
            ref = dataFromServer.results;
            for (i = 0, len = ref.length; i < len; i++) {
                studentResults = ref[i];
                if (studentResults.invalidIdentifier) {
                    invalidIdentifier.push(studentResults);
                } else if (studentResults.error) {
                    errors.push(studentResults);
                } else if (studentResults.after.enrollment) {
                    enrolled.push(studentResults);
                } else if (studentResults.after.allowed) {
                    if (studentResults.after.auto_enroll) {
                        autoenrolled.push(studentResults);
                    } else {
                        allowed.push(studentResults);
                    }
                } else if (dataFromServer.action === 'unenroll' &&
                      !studentResults.before.enrollment &&
                      !studentResults.before.allowed) {
                    notunenrolled.push(studentResults);
                } else if (!studentResults.after.enrollment) {
                    notenrolled.push(studentResults);
                } else {
                    console.warn('student results not reported to user');  // eslint-disable-line no-console
                }
            }
            renderList = function(label, ids) {
                var identifier, $idsList, $taskResSection, h, len3;
                $taskResSection = $('<div/>', {
                    class: 'request-res-section'
                });
                $taskResSection.append($('<h3/>', {
                    text: label
                }));
                $idsList = $('<ul/>');
                $taskResSection.append($idsList);
                for (h = 0, len3 = ids.length; h < len3; h++) {
                    identifier = ids[h];
                    $idsList.append($('<li/>', {
                        text: identifier
                    }));
                }
                return displayResponse.$task_response.append($taskResSection);
            };
            if (invalidIdentifier.length) {
                renderList(gettext('The following email addresses and/or usernames are invalid:'), (function() {
                    var m, len4, results;
                    results = [];
                    for (m = 0, len4 = invalidIdentifier.length; m < len4; m++) {
                        sr = invalidIdentifier[m];
                        results.push(sr.identifier);
                    }
                    return results;
                }()));
            }
            if (errors.length) {
                errorsLabel = (function() {
                    if (dataFromServer.action === 'enroll') {
                        return 'There was an error enrolling:';
                    } else if (dataFromServer.action === 'unenroll') {
                        return 'There was an error unenrolling:';
                    } else {
                        console.warn("unknown action from server '" + dataFromServer.action + "'");  // eslint-disable-line no-console, max-len
                        return 'There was an error processing:';
                    }
                }());
                renderIdsLists = function(errs) {
                    var srItem,
                        k = 0,
                        results = [];
                    for (k = 0, len = errs.length; k < len; k++) {
                        srItem = errs[k];
                        results.push(srItem.identifier);
                    }
                    return results;
                };
                for (j = 0, len1 = errors.length; j < len1; j++) {
                    studentResults = errors[j];
                    renderList(errorsLabel, renderIdsLists(errors));
                }
            }
            if (notenrolled.length && !emailStudents) {
                // Translators: A list of users appears after this sentence;
                renderList(gettext('The following users are no longer enrolled in the course:'), (function() {
                    var k, len2, results;
                    results = [];
                    for (k = 0, len2 = notenrolled.length; k < len2; k++) {
                        sr = notenrolled[k];
                        results.push(sr.identifier);
                    }
                    return results;
                }()));
            }
            if (notunenrolled.length) {
                return renderList(gettext('These users were not affiliated with the course so could not be unenrolled:'), (function() {  // eslint-disable-line max-len
                    var k, len2, results;
                    results = [];
                    for (k = 0, len2 = notunenrolled.length; k < len2; k++) {
                        sr = notunenrolled[k];
                        results.push(sr.identifier);
                    }
                    return results;
                }()));
            }
            return renderList();
        };

        return banOnCourse;
    }());

    BanUser = (function() {
        function banUser($section) {
            var thisbanuser = this;
            this.$section = $section;
            this.$section.data('wrapper', this);
            plantTimeout(0, function() {
                return new BanOnCourse(thisbanuser.$section.find('.ban-user'));
            });
        }

        banUser.prototype.onClickTitle = function() {};

        return banUser;
    }());

    _.defaults(window, {
        InstructorDashboard: {}
    });

    _.defaults(window.InstructorDashboard, {
        sections: {}
    });

    _.defaults(window.InstructorDashboard.sections, {
        BanUser: BanUser
    });
}).call(this);