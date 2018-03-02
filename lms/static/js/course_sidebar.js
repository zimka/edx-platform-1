/**
 * 
 * Courseware mobile menu
 * 
**/

$(document).ready(function(){
    $('.js-open-menu').click(function(){
        if ($(window).width() < 800 && $('.accordion').hasClass('open')) {
            $('.accordion').removeClass('open');

            console.log('show menu');   // temp
        } 
        if ($(window).width() < 800 && $('.accordion').not('.open')) {
            $('.accordion').addClass('open');

            console.log('show menu');   // temp
        } 
    });
});

$(window).resize(function(){
    if ($(window).width() > 800) {
        $('.accordion').addClass('open');
        $('.courseware-show-accordion').remove('shown');

        console.log('more 800');   // temp
    }
    if ($(window).width() < 800) {
        $('.accordion').removeClass('open');
        $('.courseware-show-accordion').addClass('shown');

        console.log('less 800');   // temp
    }
});
