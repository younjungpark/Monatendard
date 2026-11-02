cask "font-monatendard-nerd-font" do
  version "0.3.1"
  sha256 "89323c8a69b8f821c62197c5ee59f9ccbd54ac924bba9612f7eb657a8a7a4ba5"

  url "https://github.com/younjungpark/Monatendard/releases/download/v#{version}/Monatendard-v#{version}-Desktop-Nerd.zip"
  name "Monatendard Nerd Font Mono"
  desc "Monatendard with Nerd Font icons for terminals"
  homepage "https://monatendard.github.io/"

  livecheck do
    url :url
    strategy :github_latest
  end

  font "fonts/MonatendardNFM-Bold.ttf"
  font "fonts/MonatendardNFM-BoldItalic.ttf"
  font "fonts/MonatendardNFM-ExtraBold.ttf"
  font "fonts/MonatendardNFM-ExtraBoldItalic.ttf"
  font "fonts/MonatendardNFM-ExtraLight.ttf"
  font "fonts/MonatendardNFM-ExtraLightItalic.ttf"
  font "fonts/MonatendardNFM-Italic.ttf"
  font "fonts/MonatendardNFM-Light.ttf"
  font "fonts/MonatendardNFM-LightItalic.ttf"
  font "fonts/MonatendardNFM-Medium.ttf"
  font "fonts/MonatendardNFM-MediumItalic.ttf"
  font "fonts/MonatendardNFM-Regular.ttf"
  font "fonts/MonatendardNFM-SemiBold.ttf"
  font "fonts/MonatendardNFM-SemiBoldItalic.ttf"
end
