# Google Tink, pulled in by amplify_secure_storage, references annotations that
# only exist at compile time. R8 treats the dangling references as errors and
# fails the release build outright, so suppress them explicitly. Without this
# there is no release APK at all — only debug builds work.
-dontwarn com.google.errorprone.annotations.CanIgnoreReturnValue
-dontwarn com.google.errorprone.annotations.CheckReturnValue
-dontwarn com.google.errorprone.annotations.Immutable
-dontwarn com.google.errorprone.annotations.RestrictedApi
-dontwarn javax.annotation.Nullable
-dontwarn javax.annotation.concurrent.GuardedBy
