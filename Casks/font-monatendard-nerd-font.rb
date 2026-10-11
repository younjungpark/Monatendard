cask "font-monatendard-nerd-font" do
  version "0.3.0"
  sha256 "2a1f81077f6b8306801587c842eac64666bd01b7705c36490de3603b831aa0cb"

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
