cask "font-monatendard" do
  version "0.3.1"
  sha256 "c05361791d11dfac3d666e7bba7bbd09fca89cf1ac741f488a79da3ca0f56d49"

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
