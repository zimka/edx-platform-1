(function(requirejs, require, define) {
    define(
'video/02_html5_video.js',
['video/019_html5_video.js'],
function(HTML5Video) {
    HTML5Video_mod = {};
    HTML5Video_mod.PlayerState = HTML5Video.PlayerState;
    HTML5Video_mod.Player = (function() {

        Player.prototype = Object.create(HTML5Video.Player.prototype);

        Player.prototype.getAvailableQualityLevels = function(){
            return this.videoEl.find('source')["length"];
        };

        Player.prototype.setPlaybackQuality = function(value){
            if (value == "large"){
                return;
            }
            if (this.getAvailableQualityLevels() == 1){
                return;
            }
            var btn = this.el.find(".quality-control");
            var is_active = btn.hasClass("high-def");

            if (is_active){
                btn.removeClass("high-def");
                btn.find(".icon").html("SD");
            }
            else{
                btn.addClass("high-def");
                btn.find(".icon").html("HD");
            }
            var state_before_switch = this.playerState;
            var time = this.getCurrentTime();
            var sources_obj = this.videoEl.find('source');
            this.video.innerHTML = sources_obj.eq(1).prop('outerHTML') +' ' + sources_obj.eq(0).prop('outerHTML');
            var self = this;
            var g = self.pauseVideo.bind(self);
            var handler = function() {
                self.seekTo(time);
                if (state_before_switch == '2') {
                    setTimeout(g, 200);
                }
                self.video.removeEventListener('loadedmetadata', handler, false)
            };
            this.video.addEventListener('loadedmetadata', handler, false);
            this.video.load();
            this.playVideo();
        };

        return Player;

        function Player(el, config){
            HTML5Video.Player.call(this, el, config);
        }
    }());
    return HTML5Video_mod;

});
}(RequireJS.requirejs, RequireJS.require, RequireJS.define));
