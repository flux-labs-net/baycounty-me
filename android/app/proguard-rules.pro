# kotlinx.serialization keeps its generated serializers.
-keepattributes *Annotation*, InnerClasses
-dontnote kotlinx.serialization.**
-keepclassmembers class kotlinx.serialization.json.** { *** Companion; }
-keepclasseswithmembers class kotlinx.serialization.json.** { kotlinx.serialization.KSerializer serializer(...); }
-keep,includedescriptorclasses class me.baycounty.kit.**$$serializer { *; }
-keepclassmembers class me.baycounty.kit.** { *** Companion; }
-keepclasseswithmembers class me.baycounty.kit.** { kotlinx.serialization.KSerializer serializer(...); }
-dontwarn org.osmdroid.**
