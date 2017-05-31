PendingInstructorTasks = -> window.InstructorDashboard.util.PendingInstructorTasks

class @InstructorResetTrack
  constructor: (@$section) ->
    # attach self to html so that instructor_dashboard.coffee can find
    #  this object to call event handlers like 'onClickTitle'
    @$section.data 'wrapper', @

    @$table                = @$section.find "#instructor-reset-track-table table"
    @$next_table_button    = @$section.find "#instructor-reset-track-table .next-button"
    @$prev_table_button    = @$section.find "#instructor-reset-track-table .prev-button"

    # attach click handlers

    # go to student progress page
    @$next_table_button.click () =>
      url = @$next_table_button[0].value;
      $.ajax
        type: 'GET'
        dataType: 'json'
        url: url
        success: (data) =>
          results = data['results']
          @clear_table (@$table[0].rows.length-1)
          for r in results
            @add_row (r)
          @$next_table_button[0].value = data['next']
          if !(@$next_table_button[0].value=='null')
            @$next_table_button[0].addClass('disabled')
          else
            @$next_table_button[0].removeClass('disabled')

          @$prev_table_button[0].value = data['previous']
          if (@$prev_table_button[0].value=='null')
            @$prev_table_button[0].addClass('disabled')
          else
             @$prev_table_button[0].removeClass('disabled')
          return

  add_row: (row_dict) ->
    new_row = @$table[0].insertRow(0)
    cell = new_row.insertCell(0);
    cell.innerHTML = row_dict['instructor_username']

    cell = new_row.insertCell(1);
    cell.innerHTML = row_dict['student_username']

    cell = new_row.insertCell(2);
    cell.innerHTML = row_dict['block_id']

    cell = new_row.insertCell(3);
    cell.innerHTML = row_dict['action']

    cell = new_row.insertCell(4);
    cell.innerHTML = row_dict['removed_answer']

    cell = new_row.insertCell(5);
    cell.innerHTML = row_dict['timestamp']

  clear_table: (number_rows) ->
    if number_rows<=0
      return
    for i in [0..number_rows]
      @$table[0].deleteRow(1)
    return

_.defaults window, InstructorDashboard: {}
_.defaults window.InstructorDashboard, sections: {}
_.defaults window.InstructorDashboard.sections,
  InstructorResetTrack: InstructorResetTrack