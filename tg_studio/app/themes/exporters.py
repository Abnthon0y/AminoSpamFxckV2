"""Экспорт темы в форматы Telegram: Android (.attheme), Desktop (.tdesktop-theme),
iOS (.tgios-theme) и облачная тема (настройки для account.createTheme).

Мини-язык маппинга:  role | role/AA (альфа 0-100%) | roleA+roleB:0.3 (смешивание)
"""
from __future__ import annotations

import io
import re
import zipfile

from PIL import Image

from .colors import argb_int, hex_to_rgb, luminance, mix

ANDROID_MAP = """
windowBackgroundWhite=bg
windowBackgroundGray=bg2
windowBackgroundGrayShadow=bg2
windowBackgroundWhiteBlackText=text
windowBackgroundWhiteGrayText=text2
windowBackgroundWhiteGrayText2=text2
windowBackgroundWhiteGrayText3=text2
windowBackgroundWhiteGrayText4=text2
windowBackgroundWhiteGrayText5=text2
windowBackgroundWhiteGrayText6=text2
windowBackgroundWhiteGrayText7=text2
windowBackgroundWhiteGrayText8=text2
windowBackgroundWhiteHintText=text2
windowBackgroundWhiteBlueText=accent
windowBackgroundWhiteBlueText2=accent
windowBackgroundWhiteBlueText3=accent
windowBackgroundWhiteBlueText4=accent
windowBackgroundWhiteBlueText5=accent
windowBackgroundWhiteBlueText6=accent
windowBackgroundWhiteBlueText7=accent
windowBackgroundWhiteBlueHeader=accent
windowBackgroundWhiteBlueButton=accent
windowBackgroundWhiteBlueIcon=accent
windowBackgroundWhiteLinkText=link
windowBackgroundWhiteLinkSelection=selection
windowBackgroundWhiteValueText=accent
windowBackgroundWhiteGreenText=online
windowBackgroundWhiteGreenText2=online
windowBackgroundWhiteGrayIcon=icon
windowBackgroundWhiteInputField=divider
windowBackgroundWhiteInputFieldActivated=accent
windowBackgroundChecked=accent
windowBackgroundCheckText=on_accent
windowBackgroundUnchecked=bg2
divider=divider
listSelectorSDK21=text/8
graySection=bg2
key_graySectionText=text2
progressCircle=accent
fastScrollActive=accent
fastScrollInactive=divider
fastScrollText=on_accent
actionBarDefault=header
actionBarDefaultIcon=header_icon
actionBarDefaultTitle=header_text
actionBarDefaultSubtitle=header_text/70
actionBarDefaultSelector=header_text/12
actionBarWhiteSelector=text/12
actionBarDefaultSearch=header_text
actionBarDefaultSearchPlaceholder=header_text/55
actionBarDefaultSubmenuItem=text
actionBarDefaultSubmenuItemIcon=icon
actionBarDefaultSubmenuBackground=surface
actionBarDefaultSubmenuSeparator=bg2
actionBarActionModeDefault=surface
actionBarActionModeDefaultIcon=icon
actionBarActionModeDefaultTop=surface
actionBarActionModeDefaultSelector=text/12
actionBarTabActiveText=header_text
actionBarTabUnactiveText=header_text/60
actionBarTabLine=accent
actionBarTabSelector=header_text/12
actionBarBrowser=header
actionBarDefaultArchived=bg2
actionBarDefaultArchivedTitle=text
actionBarDefaultArchivedIcon=icon
avatar_backgroundActionBarBlue=header
avatar_actionBarIconBlue=header_icon
avatar_actionBarSelectorBlue=header_text/12
avatar_subtitleInProfileBlue=header_text/70
avatar_backgroundInProfileBlue=accent
avatar_text=on_accent
avatar_backgroundSaved=accent
avatar_backgroundArchived=badge_muted
avatar_backgroundArchivedHidden=badge_muted
profile_title=header_text
profile_status=text2
profile_actionBackground=accent
profile_actionIcon=on_accent
profile_actionPressedBackground=accent+bg:0.2
profile_verifiedBackground=accent
profile_verifiedCheck=on_accent
profile_tabText=text2
profile_tabSelectedText=accent
profile_tabSelectedLine=accent
profile_tabSelector=text/10
chats_name=text
chats_secretName=online
chats_secretIcon=online
chats_message=text2
chats_message_threeLines=text2
chats_messageArchived=text2
chats_nameMessage=accent
chats_nameMessage_threeLines=accent
chats_nameMessageArchived=text2
chats_nameArchived=text
chats_draft=accent
chats_attachMessage=accent
chats_actionMessage=accent
chats_date=text2
chats_pinnedIcon=icon
chats_pinnedOverlay=text/5
chats_tabletSelectedOverlay=selection/50
chats_sentCheck=accent
chats_sentReadCheck=accent
chats_sentClock=text2
chats_sentError=on_accent
chats_sentErrorIcon=on_accent
chats_verifiedBackground=accent
chats_verifiedCheck=on_accent
chats_muteIcon=icon
chats_mentionIcon=on_accent
chats_unreadCounter=accent
chats_unreadCounterText=on_accent
chats_unreadCounterMuted=badge_muted
chats_onlineCircle=online
chats_archiveBackground=accent
chats_archivePinBackground=badge_muted
chats_archiveIcon=on_accent
chats_archiveText=on_accent
chats_actionBackground=accent
chats_actionIcon=on_accent
chats_actionPressedBackground=accent+bg:0.2
chats_actionUnreadBackground=accent
chats_actionUnreadIcon=on_accent
chats_menuBackground=surface
chats_menuItemText=text
chats_menuItemIcon=icon
chats_menuItemCheck=accent
chats_menuName=header_text
chats_menuPhone=header_text/80
chats_menuPhoneCats=header_text/80
chats_menuCloud=header_text
chats_menuCloudBackgroundCats=header
chats_menuTopShadow=bg/0
chats_menuTopShadowCats=bg/0
chats_menuTopBackground=header
chats_menuTopBackgroundCats=header
chat_wallpaper=chat_bg
chat_inBubble=in_bubble
chat_inBubbleSelected=in_bubble+accent:0.12
chat_inBubbleShadow=in_bubble/0
chat_outBubble=out_bubble
chat_outBubbleGradient=out_bubble2
chat_outBubbleSelected=out_bubble+accent:0.12
chat_outBubbleShadow=out_bubble/0
chat_messageTextIn=in_text
chat_messageTextOut=out_text
chat_messageLinkIn=in_accent
chat_messageLinkOut=out_accent
chat_textSelectBackground=selection/60
chat_inTimeText=in_secondary
chat_outTimeText=out_secondary
chat_inTimeSelectedText=in_secondary
chat_outTimeSelectedText=out_secondary
chat_outSentCheck=out_secondary
chat_outSentCheckSelected=out_secondary
chat_outSentCheckRead=out_accent
chat_outSentCheckReadSelected=out_accent
chat_outSentClock=out_secondary
chat_outSentClockSelected=out_secondary
chat_inSentClock=in_secondary
chat_inSentClockSelected=in_secondary
chat_outViews=out_secondary
chat_inViews=in_secondary
chat_inReplyLine=in_accent
chat_outReplyLine=out_accent
chat_inReplyNameText=in_accent
chat_outReplyNameText=out_accent
chat_inReplyMessageText=in_text
chat_outReplyMessageText=out_text
chat_inReplyMediaMessageText=in_secondary
chat_outReplyMediaMessageText=out_secondary
chat_inForwardedNameText=in_accent
chat_outForwardedNameText=out_accent
chat_inViaBotNameText=in_accent
chat_outViaBotNameText=out_accent
chat_inPreviewLine=in_accent
chat_outPreviewLine=out_accent
chat_inSiteNameText=in_accent
chat_outSiteNameText=out_accent
chat_inContactNameText=in_accent
chat_outContactNameText=out_accent
chat_inFileNameText=in_text
chat_outFileNameText=out_text
chat_inFileInfoText=in_secondary
chat_outFileInfoText=out_secondary
chat_inFileBackground=in_accent/15
chat_outFileBackground=out_accent/15
chat_inAudioTitleText=in_text
chat_outAudioTitleText=out_text
chat_inAudioPerformerText=in_secondary
chat_outAudioPerformerText=out_secondary
chat_inAudioDurationText=in_secondary
chat_outAudioDurationText=out_secondary
chat_inAudioProgress=in_bubble
chat_outAudioProgress=out_bubble
chat_inAudioSeekbar=in_secondary/50
chat_outAudioSeekbar=out_secondary/50
chat_inAudioSeekbarFill=in_accent
chat_outAudioSeekbarFill=out_accent
chat_inAudioSeekbarSelected=in_secondary
chat_outAudioSeekbarSelected=out_secondary
chat_inVoiceSeekbar=in_secondary/50
chat_outVoiceSeekbar=out_secondary/50
chat_inVoiceSeekbarFill=in_accent
chat_outVoiceSeekbarFill=out_accent
chat_inVoiceSeekbarSelected=in_secondary
chat_outVoiceSeekbarSelected=out_secondary
chat_inLoader=in_accent
chat_outLoader=out_accent
chat_inLoaderSelected=in_accent
chat_outLoaderSelected=out_accent
chat_inMediaIcon=in_bubble
chat_outMediaIcon=out_bubble
chat_inMediaIconSelected=in_bubble
chat_outMediaIconSelected=out_bubble
chat_inMenu=in_secondary
chat_outMenu=out_secondary
chat_inInstant=in_accent
chat_outInstant=out_accent
chat_inPsaNameText=in_accent
chat_outPsaNameText=out_accent
chat_inPollCorrectAnswer=online
chat_outPollCorrectAnswer=online
chat_inPollWrongAnswer=in_secondary
chat_outPollWrongAnswer=out_secondary
chat_mediaTimeBackground=service_bg/80
chat_mediaTimeText=service_text
chat_mediaViews=service_text
chat_mediaMenu=service_text
chat_mediaSentCheck=service_text
chat_mediaSentClock=service_text
chat_mediaLoaderPhoto=service_bg/80
chat_mediaLoaderPhotoIcon=service_text
chat_serviceBackground=service_bg/80
chat_serviceBackgroundSelected=service_bg
chat_serviceText=service_text
chat_serviceLink=service_text
chat_serviceIcon=service_text
chat_unreadMessagesStartBackground=surface
chat_unreadMessagesStartText=text2
chat_unreadMessagesStartArrowIcon=text2
chat_messagePanelBackground=input_bg
chat_messagePanelText=input_text
chat_messagePanelHint=text2
chat_messagePanelCursor=accent
chat_messagePanelIcons=icon
chat_messagePanelSend=accent
chat_messagePanelVoiceLock=icon
chat_messagePanelVoiceLockBackground=surface
chat_messagePanelVoicePressed=on_accent
chat_messagePanelVoiceBackground=accent
chat_messagePanelShadow=bg/0
chat_messagePanelCancelInlineBot=icon
chat_recordedVoiceBackground=accent
chat_recordedVoiceDot=accent
chat_recordedVoicePlayPause=on_accent
chat_recordedVoiceProgress=on_accent/50
chat_recordedVoiceProgressInner=on_accent
chat_recordVoiceCancel=accent
chat_recordTime=text2
chat_emojiPanelBackground=surface
chat_emojiPanelShadowLine=divider
chat_emojiPanelEmptyText=text2
chat_emojiPanelIcon=icon
chat_emojiPanelIconSelected=accent
chat_emojiPanelStickerPackSelector=bg2
chat_emojiPanelStickerPackSelectorLine=accent
chat_emojiPanelBackspace=icon
chat_emojiPanelTrendingTitle=text
chat_emojiPanelTrendingDescription=text2
chat_emojiPanelStickerSetName=text2
chat_emojiPanelStickerSetNameIcon=icon
chat_emojiPanelBadgeBackground=accent
chat_emojiPanelBadgeText=on_accent
chat_emojiPanelNewTrending=accent
chat_emojiSearchBackground=bg2
chat_emojiSearchIcon=icon
chat_emojiBottomPanelIcon=icon
chat_emojiPanelMasksIcon=icon
chat_emojiPanelMasksIconSelected=accent
chat_goDownButton=surface
chat_goDownButtonIcon=icon
chat_goDownButtonCounter=on_accent
chat_goDownButtonCounterBackground=accent
chat_goDownButtonShadow=bg/0
chat_topPanelBackground=surface
chat_topPanelClose=icon
chat_topPanelLine=accent
chat_topPanelTitle=accent
chat_topPanelMessage=text2
chat_reportSpam=accent
chat_addContact=accent
chat_inLocationBackground=in_accent/15
chat_inLocationIcon=in_accent
chat_outLocationIcon=out_accent
chat_inContactBackground=in_accent
chat_inContactIcon=in_bubble
chat_outContactBackground=out_accent
chat_outContactIcon=out_bubble
chat_selectedBackground=selection/50
chat_secretTimeText=service_text
chat_stickerNameText=service_text
chat_botButtonText=service_text
chat_botKeyboardButtonText=text
chat_botKeyboardButtonBackground=surface
chat_botKeyboardButtonBackgroundPressed=bg2
chat_inlineResultIcon=accent
chat_attachCheckBoxBackground=accent
chat_attachCheckBoxCheck=on_accent
chat_fieldOverlayText=accent
chat_searchPanelIcons=icon
chat_searchPanelText=text
chat_status=header_text/70
chat_lockIcon=on_accent
chat_muteIcon=icon
chat_editDoneIcon=accent
dialogBackground=surface
dialogBackgroundGray=bg2
dialogTextBlack=text
dialogTextGray=text2
dialogTextGray2=text2
dialogTextGray3=text2
dialogTextGray4=text2
dialogTextHint=text2
dialogTextBlue=accent
dialogTextBlue2=accent
dialogTextBlue4=accent
dialogTextLink=link
dialogLinkSelection=selection
dialogButton=accent
dialogButtonSelector=accent/12
dialogIcon=icon
dialogGrayLine=divider
dialogTopBackground=accent
dialogInputField=divider
dialogInputFieldActivated=accent
dialogCheckboxSquareBackground=accent
dialogCheckboxSquareCheck=on_accent
dialogCheckboxSquareUnchecked=text2
dialogRadioBackground=text2
dialogRadioBackgroundChecked=accent
dialogRoundCheckBox=accent
dialogRoundCheckBoxCheck=on_accent
dialogLineProgress=accent
dialogLineProgressBackground=divider
dialogScrollGlow=bg2
dialogFloatingButton=accent
dialogFloatingButtonPressed=accent+bg:0.2
dialogFloatingIcon=on_accent
dialogShadowLine=divider
dialogSearchBackground=bg2
dialogSearchHint=text2
dialogSearchIcon=icon
dialogSearchText=text
dialogBadgeBackground=accent
dialogBadgeText=on_accent
dialogEmptyImage=text2
dialogEmptyText=text2
dialogSwipeRemove=accent
switchTrack=text2/60
switchTrackChecked=accent
switchTrackBlue=text2/60
switchTrackBlueChecked=accent
switchTrackBlueThumb=surface
switchTrackBlueThumbChecked=surface
switchTrackBlueSelector=accent/12
switchTrackBlueSelectorChecked=accent/12
switch2Track=text2/60
switch2TrackChecked=accent
checkbox=accent
checkboxCheck=on_accent
checkboxDisabled=divider
checkboxSquareBackground=accent
checkboxSquareCheck=on_accent
checkboxSquareUnchecked=text2
checkboxSquareDisabled=divider
radioBackground=text2
radioBackgroundChecked=accent
featuredStickers_addButton=accent
featuredStickers_addButtonPressed=accent+bg:0.2
featuredStickers_buttonText=on_accent
featuredStickers_addedIcon=accent
featuredStickers_buttonProgress=on_accent
featuredStickers_removeButtonText=accent
featuredStickers_unread=accent
undo_background=surface
undo_cancelColor=accent
undo_infoColor=text
inappPlayerBackground=surface
inappPlayerPlayPause=accent
inappPlayerTitle=text
inappPlayerPerformer=text2
inappPlayerClose=icon
returnToCallBackground=accent
returnToCallText=on_accent
contextProgressInner1=accent/30
contextProgressOuter1=accent
player_actionBarSelector=text/12
player_actionBarTitle=text
player_actionBarSubtitle=text2
player_actionBarItems=icon
player_background=surface
player_time=text2
player_progressBackground=divider
player_progress=accent
player_button=icon
player_buttonActive=accent
sharedMedia_linkPlaceholder=bg2
sharedMedia_linkPlaceholderText=accent
sharedMedia_photoPlaceholder=bg2
sharedMedia_startStopLoadIcon=accent
location_sendLocationBackground=accent
location_sendLocationIcon=on_accent
location_sendLiveLocationBackground=online
location_sendLiveLocationIcon=on_accent
files_folderIcon=icon
files_folderIconBackground=bg2
files_iconText=on_accent
passport_authorizeBackground=accent
passport_authorizeText=on_accent
emptyListPlaceholder=text2
picker_enabledButton=accent
picker_disabledButton=text2
picker_badge=accent
picker_badgeText=on_accent
stickers_menu=icon
stickers_menuSelector=text/12
key_chat_messagePanelVoiceLock=icon
statisticChartSignature=text2
statisticChartSignatureAlpha=text2
statisticChartHintLine=divider
statisticChartActiveLine=accent
topics_unreadCounter=accent
topics_unreadCounterMuted=badge_muted
"""

TDESKTOP_MAP = """
windowBg=surface
windowFg=text
windowBgOver=surface+text:0.06
windowBgRipple=surface+text:0.12
windowFgOver=text
windowSubTextFg=text2
windowSubTextFgOver=text2
windowBoldFg=text
windowBoldFgOver=text
windowBgActive=accent
windowFgActive=on_accent
windowActiveTextFg=accent
windowShadowFg=bg2
windowShadowFgFallback=bg2
shadowFg=bg/0
slideFadeOutBg=bg/50
imageBg=bg2
imageBgTransparent=surface
activeButtonBg=accent
activeButtonBgOver=accent+text:0.1
activeButtonBgRipple=accent+text:0.2
activeButtonFg=on_accent
activeButtonFgOver=on_accent
activeButtonSecondaryFg=on_accent
activeButtonSecondaryFgOver=on_accent
activeLineFg=accent
activeLineFgError=accent
lightButtonBg=surface
lightButtonBgOver=surface+accent:0.12
lightButtonBgRipple=surface+accent:0.22
lightButtonFg=accent
lightButtonFgOver=accent
attentionButtonFg=accent
attentionButtonFgOver=accent
attentionButtonBgOver=surface+accent:0.12
attentionButtonBgRipple=surface+accent:0.22
outlineButtonBg=surface
outlineButtonBgOver=surface+accent:0.12
outlineButtonOutlineFg=accent
outlineButtonBgRipple=surface+accent:0.22
menuBg=surface
menuBgOver=surface+text:0.07
menuBgRipple=surface+text:0.14
menuIconFg=icon
menuIconFgOver=icon
menuSubmenuArrowFg=icon
menuFgDisabled=text2
menuSeparatorFg=divider
scrollBarBg=text/30
scrollBarBgOver=text/45
scrollBg=text/8
scrollBgOver=text/12
smallCloseIconFg=icon
smallCloseIconFgOver=text
radialFg=on_accent
radialBg=bg/50
placeholderFg=text2
placeholderFgActive=text2
inputBorderFg=divider
filterInputBorderFg=accent
filterInputInactiveBg=bg2
filterInputActiveBg=surface
checkboxFg=text2
sliderBgInactive=divider
sliderBgActive=accent
tooltipBg=surface
tooltipFg=text
tooltipBorderFg=divider
titleShadow=bg/0
titleBg=header
titleBgActive=header
titleButtonBg=header
titleButtonFg=header_icon
titleButtonBgOver=header+header_text:0.1
titleButtonFgOver=header_text
titleButtonBgActive=header
titleButtonFgActive=header_icon
titleButtonBgActiveOver=header+header_text:0.1
titleButtonFgActiveOver=header_text
titleButtonCloseBg=header
titleButtonCloseFg=header_icon
titleButtonCloseBgActive=header
titleButtonCloseFgActive=header_icon
titleFg=header_text
titleFgActive=header_text
trayCounterBg=accent
trayCounterBgMute=badge_muted
trayCounterFg=on_accent
trayCounterBgMacInvert=accent
trayCounterFgMacInvert=on_accent
layerBg=bg/60
cancelIconFg=icon
cancelIconFgOver=text
boxBg=surface
boxTextFg=text
boxTextFgGood=online
boxTextFgError=accent
boxTitleFg=text
boxSearchBg=surface
boxSearchCancelIconFg=icon
boxSearchCancelIconFgOver=text
boxTitleAdditionalFg=text2
boxTitleCloseFg=icon
boxTitleCloseFgOver=text
boxDividerBg=bg2
boxDividerFg=divider
membersAboutLimitFg=text2
contactsBg=surface
contactsBgOver=surface+text:0.06
contactsNameFg=text
contactsStatusFg=text2
contactsStatusFgOver=text2
contactsStatusFgOnline=accent
photoCropFadeBg=bg/60
photoCropPointFg=text
introBg=bg
introTitleFg=text
introDescriptionFg=text2
introErrorFg=accent
introCoverTopBg=accent
introCoverBottomBg=accent
introCoverIconsFg=on_accent
introCoverPlaneTrace=on_accent/40
introCoverPlaneInner=on_accent
introCoverPlaneOuter=on_accent
introCoverPlaneTop=on_accent
dialogsMenuIconFg=icon
dialogsMenuIconFgOver=text
dialogsBg=bg
dialogsNameFg=text
dialogsChatIconFg=text
dialogsDateFg=text2
dialogsTextFg=text2
dialogsTextFgService=accent
dialogsDraftFg=accent
dialogsVerifiedIconBg=accent
dialogsVerifiedIconFg=on_accent
dialogsSendingIconFg=text2
dialogsSentIconFg=accent
dialogsUnreadBg=accent
dialogsUnreadBgMuted=badge_muted
dialogsUnreadFg=on_accent
dialogsBgOver=bg+text:0.06
dialogsNameFgOver=text
dialogsChatIconFgOver=text
dialogsDateFgOver=text2
dialogsTextFgOver=text2
dialogsTextFgServiceOver=accent
dialogsDraftFgOver=accent
dialogsVerifiedIconBgOver=accent
dialogsVerifiedIconFgOver=on_accent
dialogsSendingIconFgOver=text2
dialogsSentIconFgOver=accent
dialogsUnreadBgOver=accent
dialogsUnreadBgMutedOver=badge_muted
dialogsUnreadFgOver=on_accent
dialogsBgActive=accent
dialogsNameFgActive=on_accent
dialogsChatIconFgActive=on_accent
dialogsDateFgActive=on_accent
dialogsTextFgActive=on_accent
dialogsTextFgServiceActive=on_accent
dialogsDraftFgActive=on_accent
dialogsVerifiedIconBgActive=on_accent
dialogsVerifiedIconFgActive=accent
dialogsSendingIconFgActive=on_accent
dialogsSentIconFgActive=on_accent
dialogsUnreadBgActive=on_accent
dialogsUnreadBgMutedActive=on_accent
dialogsUnreadFgActive=accent
dialogsOnlineBadgeFg=online
dialogsRippleBg=bg+text:0.12
dialogsRippleBgActive=accent+text:0.15
dialogsForwardBg=accent
dialogsForwardFg=on_accent
searchedBarBg=bg2
searchedBarFg=text2
topBarBg=header
emojiPanBg=surface
emojiPanCategories=surface
emojiPanHeaderFg=text2
emojiPanHeaderBg=surface
emojiIconFg=icon
emojiIconFgActive=accent
stickerPanDeleteBg=bg/60
stickerPanDeleteFg=text
stickerPreviewBg=bg/80
historyTextInFg=in_text
historyTextOutFg=out_text
historyCaptionInFg=in_text
historyCaptionOutFg=out_text
historyFileNameInFg=in_text
historyFileNameOutFg=out_text
historyOutIconFg=out_accent
historyOutIconFgSelected=out_accent
historyIconFgInverted=service_text
historySendingOutIconFg=out_secondary
historySendingInIconFg=in_secondary
historySendingInvertedIconFg=service_text
historyCallArrowInFg=online
historyCallArrowOutFg=online
historyCallArrowMissedInFg=accent
historyUnreadBarBg=surface
historyUnreadBarBorder=divider
historyUnreadBarFg=text2
historyForwardChooseBg=service_bg/80
historyForwardChooseFg=service_text
historyPeer1NameFg=in_accent
historyPeer1UserpicBg=accent
historyPeerUserpicFg=on_accent
historyScrollBarBg=text/30
historyScrollBarBgOver=text/45
historyScrollBg=text/8
historyScrollBgOver=text/12
historyLinkInFg=in_accent
historyLinkOutFg=out_accent
historyComposeAreaBg=input_bg
historyComposeAreaFg=input_text
historyComposeAreaFgService=text2
historyComposeIconFg=icon
historyComposeIconFgOver=accent
historySendIconFg=accent
historySendIconFgOver=accent
historyPinnedBg=surface
historyReplyBg=input_bg
historyReplyIconFg=accent
historyReplyCancelFg=icon
historyReplyCancelFgOver=text
historyComposeButtonBg=input_bg
historyComposeButtonBgOver=input_bg+text:0.06
historyComposeButtonBgRipple=input_bg+text:0.12
historyToDownBg=surface
historyToDownBgOver=surface+text:0.06
historyToDownBgRipple=surface+text:0.12
historyToDownFg=icon
historyToDownFgOver=text
historyToDownShadow=bg/30
msgInBg=in_bubble
msgInBgSelected=in_bubble+accent:0.15
msgOutBg=out_bubble
msgOutBgSelected=out_bubble+accent:0.15
msgSelectOverlay=selection/40
msgStickerOverlay=selection/40
msgInServiceFg=in_accent
msgInServiceFgSelected=in_accent
msgOutServiceFg=out_accent
msgOutServiceFgSelected=out_accent
msgInShadow=in_bubble/0
msgInShadowSelected=in_bubble/0
msgOutShadow=out_bubble/0
msgOutShadowSelected=out_bubble/0
msgInDateFg=in_secondary
msgInDateFgSelected=in_secondary
msgOutDateFg=out_secondary
msgOutDateFgSelected=out_secondary
msgServiceFg=service_text
msgServiceBg=service_bg/80
msgServiceBgSelected=service_bg
msgInReplyBarColor=in_accent
msgInReplyBarSelColor=in_accent
msgOutReplyBarColor=out_accent
msgOutReplyBarSelColor=out_accent
msgImgReplyBarColor=service_text
msgInMonoFg=in_accent
msgOutMonoFg=out_accent
msgDateImgFg=service_text
msgDateImgBg=service_bg/70
msgDateImgBgOver=service_bg/85
msgDateImgBgSelected=service_bg
msgFileThumbLinkInFg=in_accent
msgFileThumbLinkInFgSelected=in_accent
msgFileThumbLinkOutFg=out_accent
msgFileThumbLinkOutFgSelected=out_accent
msgFileInBg=in_accent
msgFileInBgOver=in_accent
msgFileInBgSelected=in_accent
msgFileOutBg=out_accent
msgFileOutBgOver=out_accent
msgFileOutBgSelected=out_accent
msgFile1Bg=accent
msgFile1BgDark=accent
msgFile1BgOver=accent
msgFile1BgSelected=accent
msgWaveformInActive=in_accent
msgWaveformInActiveSelected=in_accent
msgWaveformInInactive=in_secondary/50
msgWaveformInInactiveSelected=in_secondary/50
msgWaveformOutActive=out_accent
msgWaveformOutActiveSelected=out_accent
msgWaveformOutInactive=out_secondary/50
msgWaveformOutInactiveSelected=out_secondary/50
msgBotKbOverBgAdd=text/10
msgBotKbIconFg=service_text
msgBotKbRippleBg=text/15
mediaInFg=in_secondary
mediaInFgSelected=in_secondary
mediaOutFg=out_secondary
mediaOutFgSelected=out_secondary
youtubePlayIconBg=accent
youtubePlayIconFg=on_accent
videoPlayIconBg=service_bg/70
videoPlayIconFg=service_text
toastBg=surface/90
toastFg=text
reportSpamBg=surface
reportSpamFg=text
historyToDownBgRipple=surface+text:0.12
profileStatusFgOver=text2
profileVerifiedCheckBg=accent
profileVerifiedCheckFg=on_accent
profileAdminStartFg=accent
notificationsBoxMonitorFg=text
notificationsBoxScreenBg=accent
notificationSampleUserpicFg=accent
notificationSampleCloseFg=icon
notificationSampleTextFg=text2
notificationSampleNameFg=text
mainMenuBg=surface
mainMenuCoverBg=header
mainMenuCoverFg=header_text
mainMenuCloudFg=header_text
mainMenuCloudBg=header+header_text:0.15
mediaPlayerBg=surface
mediaPlayerActiveFg=accent
mediaPlayerInactiveFg=divider
mediaPlayerDisabledFg=divider
mediaviewFileBg=surface
mediaviewFileNameFg=text
mediaviewFileSizeFg=text2
mediaviewFileRedCornerFg=accent
mediaviewFileYellowCornerFg=accent
mediaviewFileGreenCornerFg=accent
mediaviewFileBlueCornerFg=accent
mediaviewFileExtFg=on_accent
sideBarBg=bg2
sideBarBgActive=bg2+accent:0.25
sideBarBgRipple=bg2+text:0.12
sideBarTextFg=text2
sideBarTextFgActive=accent
sideBarIconFg=icon
sideBarIconFgActive=accent
sideBarBadgeBg=accent
sideBarBadgeBgMuted=badge_muted
sideBarBadgeFg=on_accent
callBg=bg/95
callNameFg=text
callFingerprintBg=bg/60
callStatusFg=text2
callIconFg=text
callAnswerBg=online
callAnswerRipple=online
callAnswerBgOuter=online/30
callHangupBg=accent
callHangupRipple=accent
callCancelBg=surface
callCancelFg=text2
callCancelRipple=surface
callMuteRipple=surface
callBarBg=accent
callBarMuteRipple=accent
callBarBgMuted=badge_muted
callBarUnmuteRipple=badge_muted
callBarFg=on_accent
importantTooltipBg=surface
importantTooltipFg=text
importantTooltipFgLink=accent
"""


def _parse_map(text: str) -> list[tuple[str, str]]:
    out = []
    for line in text.strip().splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            out.append((k.strip(), v.strip()))
    return out


def _resolve(expr: str, roles: dict) -> tuple[str, int]:
    """→ (hex, alpha 0..255)."""
    alpha = 255
    if "/" in expr:
        expr, a = expr.split("/")
        alpha = round(int(a) * 2.55)
    m = re.match(r"(\w+)\+(\w+):([\d.]+)$", expr)
    if m:
        return mix(roles[m.group(1)], roles[m.group(2)], float(m.group(3))), alpha
    return roles[expr], alpha


def to_attheme(roles: dict, wallpaper: bytes | None = None) -> bytes:
    lines = []
    for key, expr in _parse_map(ANDROID_MAP):
        hx, a = _resolve(expr, roles)
        lines.append(f"{key}={argb_int(hx, a)}")
    data = ("\n".join(lines) + "\n").encode()
    if wallpaper:
        jpg = _to_jpeg(wallpaper, (1440, 2560))
        data += b"WPS\n" + jpg + b"\nWPE\n"
    return data


def to_tdesktop_palette(roles: dict) -> str:
    lines = ["// Telegram Desktop palette — сгенерировано TG Studio"]
    for key, expr in _parse_map(TDESKTOP_MAP):
        hx, a = _resolve(expr, roles)
        suffix = "" if a == 255 else f"{a:02x}"
        lines.append(f"{key}: {hx}{suffix};")
    return "\n".join(lines) + "\n"


def to_tdesktop_theme(roles: dict, wallpaper: bytes | None = None) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("colors.tdesktop-theme", to_tdesktop_palette(roles))
        if wallpaper:
            z.writestr("background.jpg", _to_jpeg(wallpaper, (2560, 1600)))
        else:
            z.writestr("background.jpg", _solid_jpeg(roles["chat_bg"]))
    return buf.getvalue()


def _h(c: str) -> str:
    return c.lstrip("#").lower()


def to_tgios(roles: dict, name: str = "TG Studio") -> str:
    r = {k: _h(v) for k, v in roles.items() if isinstance(v, str)}
    dark = luminance(roles["bg"]) < 0.3
    status = "white" if dark else "black"
    bubble = lambda bg, stroke: (f"        withWp:\n          bg: {bg}\n          highlightedBg: {stroke}\n"
                                 f"          stroke: {bg}\n          shadow: {bg}\n"
                                 f"        withoutWp:\n          bg: {bg}\n          highlightedBg: {stroke}\n"
                                 f"          stroke: {bg}\n          shadow: {bg}\n")

    def msg(side):
        p = "in" if side == "incoming" else "out"
        b = r[f"{p}_bubble"]
        hl = _h(mix(roles[f"{p}_bubble"], roles["accent"], 0.15))
        return (f"    {side}:\n      bubble:\n{bubble(b, hl)}"
                f"      primaryText: {r[f'{p}_text']}\n      secondaryText: {r[f'{p}_secondary']}\n"
                f"      linkText: {r[f'{p}_accent']}\n      linkHighlight: {r[f'{p}_accent']}\n"
                f"      scam: {r[f'{p}_accent']}\n      textHighlight: {r['selection']}\n"
                f"      accentText: {r[f'{p}_accent']}\n      accentControl: {r[f'{p}_accent']}\n"
                f"      mediaActiveControl: {r[f'{p}_accent']}\n      mediaInactiveControl: {r[f'{p}_secondary']}\n"
                f"      mediaControlInnerBg: {b}\n      pendingActivity: {r[f'{p}_secondary']}\n"
                f"      fileTitle: {r[f'{p}_text']}\n      fileDescription: {r[f'{p}_secondary']}\n"
                f"      fileDuration: {r[f'{p}_secondary']}\n      mediaPlaceholder: {r['bg2']}\n"
                f"      actionButtonsBg:\n        withWp: {r['service_bg']}\n        withoutWp: {r['service_bg']}\n"
                f"      actionButtonsStroke:\n        withWp: {r['service_bg']}\n        withoutWp: {r['service_bg']}\n"
                f"      actionButtonsText:\n        withWp: {r['service_text']}\n        withoutWp: {r['service_text']}\n"
                f"      textSelection: {r['selection']}\n      textSelectionKnob: {r['accent']}\n")

    return f"""name: {name}
basedOn: {"night" if dark else "day"}
dark: {"true" if dark else "false"}
intro:
  statusBar: {status}
  primaryText: {r['text']}
  accentText: {r['accent']}
  disabledText: {r['text2']}
  startButton: {r['accent']}
  dot: {r['text2']}
passcode:
  bg:
    top: {r['bg']}
    bottom: {r['bg2']}
  button: {r['surface']}
root:
  statusBar: {status}
  tabBar:
    background: {r['surface']}
    separator: {r['divider']}
    icon: {r['icon']}
    selectedIcon: {r['accent']}
    text: {r['text2']}
    selectedText: {r['accent']}
    badgeBackground: {r['accent']}
    badgeStroke: {r['accent']}
    badgeText: {r['on_accent']}
  navBar:
    button: {r['header_icon']}
    disabledButton: {r['text2']}
    primaryText: {r['header_text']}
    secondaryText: {r['header_text']}
    control: {r['header_icon']}
    accentText: {r['accent']}
    background: {r['header']}
    separator: {r['divider']}
    badgeFill: {r['accent']}
    badgeStroke: {r['accent']}
    badgeText: {r['on_accent']}
  searchBar:
    background: {r['bg']}
    accent: {r['accent']}
    inputFill: {r['input_bg']}
    inputText: {r['input_text']}
    inputPlaceholderText: {r['text2']}
    inputIcon: {r['icon']}
    inputClearButton: {r['icon']}
    separator: {r['divider']}
  keyboard: {"dark" if dark else "light"}
list:
  blocksBg: {r['bg2']}
  plainBg: {r['bg']}
  primaryText: {r['text']}
  secondaryText: {r['text2']}
  disabledText: {r['text2']}
  accent: {r['accent']}
  highlighted: {r['accent']}
  destructive: {r['accent']}
  placeholderText: {r['text2']}
  itemBlocksBg: {r['surface']}
  itemHighlightedBg: {r['selection']}
  blocksSeparator: {r['divider']}
  plainSeparator: {r['divider']}
  disclosureArrow: {r['icon']}
  sectionHeaderText: {r['text2']}
  freeText: {r['text2']}
  freeTextError: {r['accent']}
  freeTextSuccess: {r['online']}
  freeMonoIcon: {r['icon']}
  switch:
    frame: {r['divider']}
    handle: {r['surface']}
    content: {r['accent']}
    positive: {r['online']}
    negative: {r['accent']}
  check:
    bg: {r['accent']}
    stroke: {r['text2']}
    fg: {r['on_accent']}
  controlSecondary: {r['text2']}
  mediaPlaceholder: {r['bg2']}
  scrollIndicator: {r['text2']}
  pageIndicatorInactive: {r['divider']}
  inputClearButton: {r['icon']}
chatList:
  bg: {r['bg']}
  itemSeparator: {r['divider']}
  itemBg: {r['bg']}
  pinnedItemBg: {r['bg2']}
  itemHighlightedBg: {r['selection']}
  itemSelectedBg: {r['selection']}
  title: {r['text']}
  secretTitle: {r['online']}
  dateText: {r['text2']}
  authorName: {r['text']}
  messageText: {r['text2']}
  messageHighlightedText: {r['text']}
  messageDraftText: {r['accent']}
  checkmark: {r['accent']}
  pendingIndicator: {r['text2']}
  failedFill: {r['accent']}
  failedForeground: {r['on_accent']}
  muteIcon: {r['icon']}
  unreadBadgeActiveBg: {r['accent']}
  unreadBadgeActiveText: {r['on_accent']}
  unreadBadgeInactiveBg: {r['badge_muted']}
  unreadBadgeInactiveText: {r['bg']}
  reactionBadgeActiveBg: {r['accent']}
  pinnedBadge: {r['icon']}
  pinnedSearchBar: {r['input_bg']}
  regularSearchBar: {r['input_bg']}
  sectionHeaderBg: {r['bg2']}
  sectionHeaderText: {r['text2']}
  verifiedIconBg: {r['accent']}
  verifiedIconFg: {r['on_accent']}
  secretIcon: {r['online']}
  onlineDot: {r['online']}
chat:
  defaultWallpaper: {r['chat_bg']}
  animateMessageColors: false
  message:
{msg('incoming')}{msg('outgoing')}    freeform:
      withWp:
        bg: {r['surface']}
        highlightedBg: {r['selection']}
        stroke: {r['surface']}
        shadow: {r['surface']}
      withoutWp:
        bg: {r['surface']}
        highlightedBg: {r['selection']}
        stroke: {r['surface']}
        shadow: {r['surface']}
    infoPrimaryText: {r['text']}
    infoLinkText: {r['link']}
    outgoingCheck: {r['out_accent']}
    mediaDateAndStatusBg: {r['service_bg']}
    mediaDateAndStatusText: {r['service_text']}
    shareButtonBg:
      withWp: {r['service_bg']}
      withoutWp: {r['service_bg']}
    shareButtonStroke:
      withWp: {r['service_bg']}
      withoutWp: {r['service_bg']}
    shareButtonFg:
      withWp: {r['service_text']}
      withoutWp: {r['service_text']}
    mediaOverlayControl:
      fill: {r['service_bg']}
      foreground: {r['service_text']}
    selectionControl:
      fill: {r['accent']}
      stroke: {r['service_text']}
      foreground: {r['on_accent']}
    deliveryFailed:
      fill: {r['accent']}
      foreground: {r['on_accent']}
    mediaHighlightOverlay: {r['selection']}
  serviceMessage:
    components:
      withDefaultWp:
        bg: {r['service_bg']}
        primaryText: {r['service_text']}
        linkHighlight: {r['service_text']}
        scam: {r['accent']}
        dateFillStatic: {r['service_bg']}
        dateFillFloating: {r['service_bg']}
      withCustomWp:
        bg: {r['service_bg']}
        primaryText: {r['service_text']}
        linkHighlight: {r['service_text']}
        scam: {r['accent']}
        dateFillStatic: {r['service_bg']}
        dateFillFloating: {r['service_bg']}
    unreadBarBg: {r['surface']}
    unreadBarStroke: {r['surface']}
    unreadBarText: {r['text2']}
    dateText:
      withWp: {r['service_text']}
      withoutWp: {r['service_text']}
  inputPanel:
    panelBg: {r['input_bg']}
    panelSeparator: {r['divider']}
    panelControlAccent: {r['accent']}
    panelControl: {r['icon']}
    panelControlDisabled: {r['text2']}
    panelControlDestructive: {r['accent']}
    inputBg: {r['bg']}
    inputStroke: {r['divider']}
    inputPlaceholder: {r['text2']}
    inputText: {r['input_text']}
    inputControl: {r['icon']}
    actionControlBg: {r['accent']}
    actionControlFg: {r['on_accent']}
    primaryText: {r['text']}
    secondaryText: {r['text2']}
    mediaRecordingDot: {r['accent']}
    mediaRecordingControl:
      button: {r['accent']}
      micLevel: {r['accent']}
      activeIcon: {r['on_accent']}
  inputMediaPanel:
    panelSeparator: {r['divider']}
    panelIcon: {r['icon']}
    panelHighlightedIconBg: {r['selection']}
    panelHighlightedIcon: {r['accent']}
    panelContentVibrantOverlay: {r['text2']}
    panelContentControlVibrantOverlay: {r['text2']}
    stickersBg: {r['surface']}
    stickersSectionText: {r['text2']}
    stickersSearchBg: {r['input_bg']}
    stickersSearchPlaceholder: {r['text2']}
    stickersSearchPrimary: {r['text']}
    stickersSearchControl: {r['icon']}
    gifsBg: {r['surface']}
  inputButtonPanel:
    panelBg: {r['surface']}
    panelSeparator: {r['divider']}
    buttonBg: {r['bg2']}
    buttonHighlightedBg: {r['selection']}
    buttonStroke: {r['bg2']}
    buttonHighlightedStroke: {r['selection']}
    buttonText: {r['text']}
  historyNavigation:
    bg: {r['surface']}
    stroke: {r['divider']}
    foreground: {r['icon']}
    badgeBg: {r['accent']}
    badgeStroke: {r['accent']}
    badgeText: {r['on_accent']}
actionSheet:
  dim: 000000
  bgType: {"dark" if dark else "light"}
  opaqueItemBg: {r['surface']}
  itemBg: {r['surface']}
  opaqueItemHighlightedBg: {r['selection']}
  itemHighlightedBg: {r['selection']}
  opaqueItemSeparator: {r['divider']}
  standardActionText: {r['accent']}
  destructiveActionText: {r['accent']}
  disabledActionText: {r['text2']}
  primaryText: {r['text']}
  secondaryText: {r['text2']}
  controlAccent: {r['accent']}
  inputBg: {r['input_bg']}
  inputHollowBg: {r['input_bg']}
  inputBorder: {r['divider']}
  inputPlaceholder: {r['text2']}
  inputText: {r['input_text']}
  inputClearButton: {r['icon']}
  checkContent: {r['on_accent']}
contextMenu:
  dim: 000000
  background: {r['surface']}
  itemSeparator: {r['divider']}
  sectionSeparator: {r['bg2']}
  itemBg: {r['surface']}
  itemHighlightedBg: {r['selection']}
  primary: {r['text']}
  secondary: {r['text2']}
  destructive: {r['accent']}
  badgeFill: {r['accent']}
  badgeForeground: {r['on_accent']}
  badgeInactiveFill: {r['badge_muted']}
  badgeInactiveForeground: {r['bg']}
  extractedTint: {r['surface']}
notification:
  bg: {r['surface']}
  primaryText: {r['text']}
  expandedNotification:
    bgType: {"dark" if dark else "light"}
    navBar:
      background: {r['header']}
      primaryText: {r['header_text']}
      control: {r['header_icon']}
      separator: {r['divider']}
"""


def cloud_theme_settings(roles: dict) -> dict:
    """Параметры InputThemeSettings для облачной кросс-платформенной темы."""
    dark = luminance(roles["bg"]) < 0.3
    msg_colors = [roles["out_bubble"]]
    if roles.get("out_bubble2") and roles["out_bubble2"] != roles["out_bubble"]:
        msg_colors.append(roles["out_bubble2"])
    return {
        "base_theme": "night" if dark else "day",
        "accent_color": roles["accent"],
        "outbox_accent_color": roles["out_accent"],
        "message_colors": msg_colors,
    }


def _to_jpeg(data: bytes, max_size) -> bytes:
    im = Image.open(io.BytesIO(data)).convert("RGB")
    im.thumbnail(max_size)
    out = io.BytesIO()
    im.save(out, "JPEG", quality=90)
    return out.getvalue()


def _solid_jpeg(hx: str) -> bytes:
    im = Image.new("RGB", (64, 64), hex_to_rgb(hx))
    out = io.BytesIO()
    im.save(out, "JPEG", quality=95)
    return out.getvalue()


def palette_png(palette: list[dict]) -> bytes:
    """Карточка палитры для сохранения/шаринга."""
    from PIL import ImageDraw
    n = max(1, len(palette))
    w, h = 120 * n, 200
    im = Image.new("RGB", (w, h), "#111111")
    d = ImageDraw.Draw(im)
    for i, p in enumerate(palette):
        d.rectangle([i * 120, 0, (i + 1) * 120, 160], fill=p["hex"])
        d.text((i * 120 + 10, 170), p["hex"], fill="#eeeeee")
    out = io.BytesIO()
    im.save(out, "PNG")
    return out.getvalue()

