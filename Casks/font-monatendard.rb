cask "font-monatendard" do
  version "0.4.0"
  sha256 "fe514af8d973ab664beb5395591331d2201bb9b9b909758ca2e1b3a805b63cc9"

  url "https://github.com/younjungpark/Monatendard/releases/download/v#{version}/Monatendard-v#{version}-Desktop.zip"
  name "Monatendard"
  desc "Korean coding font combining Monaspace Neon and Pretendard"
  homepage "https://monatendard.github.io/"

  livecheck do
    url :url
    strategy :github_latest
  end

  font "fonts/Monatendard-Bold.ttf"
  font "fonts/Monatendard-BoldItalic.ttf"
  font "fonts/Monatendard-ExtraBold.ttf"
  font "fonts/Monatendard-ExtraBoldItalic.ttf"
  font "fonts/Monatendard-ExtraLight.ttf"
  font "fonts/Monatendard-ExtraLightItalic.ttf"
  font "fonts/Monatendard-Italic.ttf"
  font "fonts/Monatendard-Light.ttf"
  font "fonts/Monatendard-LightItalic.ttf"
  font "fonts/Monatendard-Medium.ttf"
  font "fonts/Monatendard-MediumItalic.ttf"
  font "fonts/Monatendard-Regular.ttf"
  font "fonts/Monatendard-SemiBold.ttf"
  font "fonts/Monatendard-SemiBoldItalic.ttf"
end
