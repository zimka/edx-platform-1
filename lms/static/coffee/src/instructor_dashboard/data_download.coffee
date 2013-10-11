###
Data Download Section

imports from other modules.
wrap in (-> ... apply) to defer evaluation
such that the value can be defined later than this assignment (file load order).
###

plantTimeout = -> window.InstructorDashboard.util.plantTimeout.apply this, arguments
std_ajax_err = -> window.InstructorDashboard.util.std_ajax_err.apply this, arguments


# Data Download Section
class DataDownload
  constructor: (@$section) ->
    # gather elements
    @$display                = @$section.find '.data-display'
    @$display_text           = @$display.find '.data-display-text'
    @$display_table          = @$display.find '.data-display-table'
    @$request_response_error = @$display.find '.request-response-error'
    @$list_studs_btn = @$section.find("input[name='list-profiles']'")
    @$list_anon_btn = @$section.find("input[name='list-anon-ids']'")
    @$grade_config_btn = @$section.find("input[name='dump-gradeconf']'")
    @$oe_data_download_btn = @$section.find("input[name='get-open-ended-data-url']'")
    @$oe_display                = @$section.find '.oe-data-display'
    @$oe_display_text           = @$oe_display.find '.data-display-text'
    @$oe_request_response_error = @$oe_display.find '.request-response-error'

    # attach click handlers

    # The list-anon case is always CSV
    @$list_anon_btn.click (e) =>
      url = @$list_anon_btn.data 'endpoint'
      location.href = url

    # This handler properly calls the api endpoint for open ended data.
    # Displays an error if there is a problem fetching the data,
    # and a link to the data otherwise.
    @$oe_data_download_btn.click (e) =>
      url = @$oe_data_download_btn.data 'endpoint'
      $.ajax
        dataType: 'json'
        url: url
        error: std_ajax_err =>
          @clear_oe_display()
          @$oe_request_response_error.text gettext("Error getting open response assessment data.  Please notify technical support if this persists.")
        success: (data) =>
          @clear_oe_display()
          if data.success == true
            button_text = gettext("Click to download data")
            @$oe_display_text.html "<a href='" + data.file_url + "' target='_blank'>" + button_text + "</a>"
          else
            @$oe_request_response_error.text gettext("No open response assessment data is available.  Please check again later.")

    # this handler binds to both the download
    # and the csv button
    @$list_studs_btn.click (e) =>
      url = @$list_studs_btn.data 'endpoint'

      # handle csv special case
      if $(e.target).data 'csv'
        # redirect the document to the csv file.
        url += '/csv'
        location.href = url
      else
        @clear_display()
        @$display_table.text 'Loading...'

        # fetch user list
        $.ajax
          dataType: 'json'
          url: url
          error: std_ajax_err =>
            @clear_display()
            @$request_response_error.text "Error getting student list."
          success: (data) =>
            @clear_display()

            # display on a SlickGrid
            options =
              enableCellNavigation: true
              enableColumnReorder: false
              forceFitColumns: true

            columns = ({id: feature, field: feature, name: feature} for feature in data.queried_features)
            grid_data = data.students

            $table_placeholder = $ '<div/>', class: 'slickgrid'
            @$display_table.append $table_placeholder
            grid = new Slick.Grid($table_placeholder, grid_data, columns, options)
            # grid.autosizeColumns()

    @$grade_config_btn.click (e) =>
      url = @$grade_config_btn.data 'endpoint'
      # display html from grading config endpoint
      $.ajax
        dataType: 'json'
        url: url
        error: std_ajax_err =>
          @clear_display()
          @$request_response_error.text "Error getting grading configuration."
        success: (data) =>
          @clear_display()
          @$display_text.html data['grading_config_summary']


  clear_display: ->
    @$display_text.empty()
    @$display_table.empty()
    @$request_response_error.empty()

  clear_oe_display: ->
    @$oe_display_text.empty()
    @$oe_request_response_error.empty()


# export for use
# create parent namespaces if they do not already exist.
# abort if underscore can not be found.
if _?
  _.defaults window, InstructorDashboard: {}
  _.defaults window.InstructorDashboard, sections: {}
  _.defaults window.InstructorDashboard.sections,
    DataDownload: DataDownload
