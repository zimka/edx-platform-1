PendingInstructorTasks = -> window.InstructorDashboard.util.PendingInstructorTasks

class @InstructorResetTrack
  constructor: (@$section) ->
    # attach self to html so that instructor_dashboard.coffee can find
    #  this object to call event handlers like 'onClickTitle'
    @$section.data 'wrapper', @

    @$table                = @$section.find "#instructor-reset-track-table table"
    @$next_table_button    = @$section.find "#instructor-reset-track-table .next-button"
    @$prev_table_button    = @$section.find "#instructor-reset-track-table .prev-button"
    @$table_pages          = @$section.find "#instructor-reset-track-table .table-pages"

    # attach click handlers

    # go to student progress page
    @$next_table_button.click () =>
      url = @$next_table_button.attr("value")
      @update_table (url)
      return

    @$prev_table_button.click () =>
      url = @$prev_table_button.attr("value")
      @update_table (url)
      return

    @$next_table_button.click()

  update_table: (url) =>
     $.ajax
        type: 'GET'
        dataType: 'json'
        url: url
        success: (data) =>
          results = data['results']
          @clear_table (@$table[0].rows.length-1)
          for r in results
            @add_row (r)
          @$next_table_button.attr("value",data['next'])
          @$prev_table_button.attr("value",data['previous'])

          if !(@$next_table_button.attr("value"))
            @$next_table_button.addClass('disabled')
          else
            @$next_table_button.removeClass('disabled')

          if !(@$prev_table_button.attr("value"))
            @$prev_table_button.addClass('disabled')
          else
             @$prev_table_button.removeClass('disabled')

          pages = @$table_pages[0]
          current = data['current_page']
          maximum = data['num_pages']
          pages.innerHTML = "#{current}/#{maximum}"
          return

  add_row: (row_dict) ->
    new_row = @$table[0].insertRow(@$table[0].rows.length)
    cell = new_row.insertCell(0);
    cell.innerHTML = row_dict['instructor_username']

    cell = new_row.insertCell(1);
    cell.innerHTML = row_dict['student_username']

    cell = new_row.insertCell(2);
    url = row_dict['block_url']
    cell.innerHTML = "<a href='#{url}'>" + row_dict['block_id'] + "</a>"

    cell = new_row.insertCell(3);
    cell.innerHTML = row_dict['action']

    cell = new_row.insertCell(4);
    cell.innerHTML = row_dict['removed_answer']

    cell = new_row.insertCell(5);
    cell.innerHTML = row_dict['time_readable']
    return

  clear_table: (number_rows) ->
    if number_rows<=0
      return
    for i in [0..number_rows-1]
      @$table[0].deleteRow(1)
    return

_.defaults window, InstructorDashboard: {}
_.defaults window.InstructorDashboard, sections: {}
_.defaults window.InstructorDashboard.sections,
  InstructorResetTrack: InstructorResetTrack