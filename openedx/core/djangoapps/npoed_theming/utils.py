from xmodule.contentstore.django import contentstore
from xmodule.modulestore.django import modulestore


def get_custom_course_assets_urls(course):
    def get_custom_from_course_key(key):
        content, num = contentstore().get_all_content_for_course(course_key=key)
        custom_js = [x for x in content if "custom_course.js" in x['displayname']] or [None]
        custom_css = [x for x in content if "custom_course.css" in x['displayname']] or [None]
        return custom_js[0], custom_css[0]
    course_key = course.id
    custom_js, custom_css = get_custom_from_course_key(course_key)

    if False:  # not (custom_js or custom_css): - currently turned off
        org_course_keys = [course.id for course in modulestore().get_courses() if course.org == course.org]
        for key in org_course_keys:
            custom_js, custom_css = get_custom_from_course_key(key)
            if custom_js or custom_css:
                break
    url = "/assets/courseware/{hash}/{location}/{name}"
    asset_url_lambda = lambda x: url.format(hash=x['md5'], location=x['filename'].split('@custom_course')[0],
                                            name=x['displayname'])
    asset_urls = {
        "js": custom_js and asset_url_lambda(custom_js),
        "css": custom_css and asset_url_lambda(custom_css)
    }
    return asset_urls
