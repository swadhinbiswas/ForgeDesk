/// MIME type lookup for web application assets.
///
/// Maps file extensions to their corresponding MIME types.
/// Covers all common web asset types including HTML, JS, CSS,
/// images, fonts, media, and WebAssembly.
pub fn mime_from_path(path: &str) -> &'static str {
    if path.ends_with(".html") || path.ends_with(".htm") {
        "text/html"
    } else if path.ends_with(".js") || path.ends_with(".mjs") {
        "application/javascript"
    } else if path.ends_with(".css") {
        "text/css"
    } else if path.ends_with(".json") {
        "application/json"
    } else if path.ends_with(".svg") {
        "image/svg+xml"
    } else if path.ends_with(".png") {
        "image/png"
    } else if path.ends_with(".jpg") || path.ends_with(".jpeg") {
        "image/jpeg"
    } else if path.ends_with(".gif") {
        "image/gif"
    } else if path.ends_with(".webp") {
        "image/webp"
    } else if path.ends_with(".ico") {
        "image/x-icon"
    } else if path.ends_with(".woff") {
        "font/woff"
    } else if path.ends_with(".woff2") {
        "font/woff2"
    } else if path.ends_with(".ttf") {
        "font/ttf"
    } else if path.ends_with(".otf") {
        "font/otf"
    } else if path.ends_with(".wasm") {
        "application/wasm"
    } else if path.ends_with(".map") {
        "application/json"
    } else if path.ends_with(".xml") {
        "application/xml"
    } else if path.ends_with(".txt") {
        "text/plain"
    } else if path.ends_with(".mp4") {
        "video/mp4"
    } else if path.ends_with(".webm") {
        "video/webm"
    } else if path.ends_with(".mp3") {
        "audio/mpeg"
    } else if path.ends_with(".ogg") {
        "audio/ogg"
    } else {
        "application/octet-stream"
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_html_mime() {
        assert_eq!(mime_from_path("/index.html"), "text/html");
        assert_eq!(mime_from_path("/page.htm"), "text/html");
    }

    #[test]
    fn test_javascript_mime() {
        assert_eq!(mime_from_path("/app.js"), "application/javascript");
        assert_eq!(mime_from_path("/module.mjs"), "application/javascript");
    }

    #[test]
    fn test_css_mime() {
        assert_eq!(mime_from_path("/style.css"), "text/css");
    }

    #[test]
    fn test_json_mime() {
        assert_eq!(mime_from_path("/data.json"), "application/json");
        assert_eq!(mime_from_path("/bundle.js.map"), "application/json");
    }

    #[test]
    fn test_image_mimes() {
        assert_eq!(mime_from_path("/logo.png"), "image/png");
        assert_eq!(mime_from_path("/photo.jpg"), "image/jpeg");
        assert_eq!(mime_from_path("/photo.jpeg"), "image/jpeg");
        assert_eq!(mime_from_path("/animation.gif"), "image/gif");
        assert_eq!(mime_from_path("/image.webp"), "image/webp");
        assert_eq!(mime_from_path("/icon.svg"), "image/svg+xml");
        assert_eq!(mime_from_path("/favicon.ico"), "image/x-icon");
    }

    #[test]
    fn test_font_mimes() {
        assert_eq!(mime_from_path("/font.woff"), "font/woff");
        assert_eq!(mime_from_path("/font.woff2"), "font/woff2");
        assert_eq!(mime_from_path("/font.ttf"), "font/ttf");
        assert_eq!(mime_from_path("/font.otf"), "font/otf");
    }

    #[test]
    fn test_media_mimes() {
        assert_eq!(mime_from_path("/video.mp4"), "video/mp4");
        assert_eq!(mime_from_path("/video.webm"), "video/webm");
        assert_eq!(mime_from_path("/audio.mp3"), "audio/mpeg");
        assert_eq!(mime_from_path("/audio.ogg"), "audio/ogg");
    }

    #[test]
    fn test_special_mimes() {
        assert_eq!(mime_from_path("/module.wasm"), "application/wasm");
        assert_eq!(mime_from_path("/config.xml"), "application/xml");
        assert_eq!(mime_from_path("/readme.txt"), "text/plain");
    }

    #[test]
    fn test_unknown_extension() {
        assert_eq!(mime_from_path("/file.xyz"), "application/octet-stream");
        assert_eq!(mime_from_path("/noext"), "application/octet-stream");
    }
}
