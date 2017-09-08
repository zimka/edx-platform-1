(function(requirejs, require, define) {
    'use strict';
    define(
'video/05_video_quality_control.js',
['video/049_video_quality_control.js'],
function(VideoQualityControl) {
    return function(state) {
        var old_videoType = state.videoType;
        var dfd = null;
        if (old_videoType == 'html5'){
            state.videoType = 'youtube';
            dfd = VideoQualityControl.call(this, state);
        }
        else {
            dfd = VideoQualityControl.call(this, state);
            return dfd;
        }
        state.videoQualityControl.el.find('.icon').html("SD");
        state.videoType = old_videoType;
        state.videoQualityControl.quality = 'large';
        state.videoQualityControl.showQualityControl();
        return dfd;
    };
});
}(RequireJS.requirejs, RequireJS.require, RequireJS.define));
